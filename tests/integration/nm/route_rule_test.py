# SPDX-License-Identifier: Apache-2.0

import json
import socket
import struct
from contextlib import contextmanager
from ipaddress import ip_network

import libnmstate
from libnmstate.error import NmstateVerificationError
import pytest
import yaml

from ..testlib.cmdlib import exec_cmd
from ..testlib.retry import retry_till_true_or_timeout

EXTERNAL_RULE_TABLE = 500
UNRELATED_RULE_TABLE = 501
RULE_PRIORITY = 100
NM_DBUS_NAME = "org.freedesktop.NetworkManager"
NM_DBUS_PATH = "/org/freedesktop/NetworkManager"


@pytest.fixture(params=["ipv4", "ipv6"])
def rule_family(request):
    return request.param


@pytest.fixture
def routing_rule_checkpoints_supported():
    command = ["busctl", "call", NM_DBUS_NAME, NM_DBUS_PATH, NM_DBUS_NAME]
    rc, output, error = exec_cmd(
        command + ["CheckpointCreate", "aouu", "0", "60", "64"]
    )
    if rc == 0:
        checkpoint = json.loads(output.split(maxsplit=1)[1])
        exec_cmd(command + ["CheckpointDestroy", "o", checkpoint], check=True)
        return True
    assert "invalid flags" in error.lower(), error
    return False


@pytest.fixture
def nm_with_routing_rule_checkpoints(routing_rule_checkpoints_supported):
    if not routing_rule_checkpoints_supported:
        pytest.skip("NetworkManager lacks routing rule checkpoints")


@pytest.fixture
def nm_without_routing_rule_checkpoints(routing_rule_checkpoints_supported):
    if routing_rule_checkpoints_supported:
        pytest.skip("NetworkManager supports routing rule checkpoints")


def _rule(family, host, table=EXTERNAL_RULE_TABLE):
    source = (
        f"192.0.2.{host}/32" if family == "ipv4" else f"2001:db8:1::{host}/128"
    )
    return {
        "family": family,
        "ip-from": source,
        "priority": RULE_PRIORITY,
        "route-table": table,
    }


def _ip_rule_command(family, operation, rule):
    command = [
        "ip",
        "-4" if family == "ipv4" else "-6",
        "rule",
        operation,
        "priority",
        str(rule["priority"]),
        "from",
        rule["ip-from"],
        "table",
        str(rule["route-table"]),
    ]
    if "fwmark" in rule:
        command += ["fwmark", f"{rule['fwmark']}/{rule['fwmask']}"]
    return command


def _kernel_rules(family, include_defaults=False):
    rules = json.loads(
        exec_cmd(
            [
                "ip",
                "-4" if family == "ipv4" else "-6",
                "-details",
                "-json",
                "rule",
            ],
            check=True,
        )[1]
    )
    if include_defaults:
        return rules
    return [
        rule
        for rule in rules
        if str(rule.get("table"))
        in (str(EXTERNAL_RULE_TABLE), str(UNRELATED_RULE_TABLE))
    ]


def _assert_kernel_rules(family, expected):
    actual = _kernel_rules(family)
    assert sorted(
        (str(ip_network(rule["src"])), rule["priority"], int(rule["table"]))
        for rule in actual
    ) == sorted(
        (rule["ip-from"], rule["priority"], rule["route-table"])
        for rule in expected
    ), actual


def _add_duplicate_rule(rule):
    source = ip_network(rule["ip-from"])
    family = socket.AF_INET if source.version == 4 else socket.AF_INET6
    payload = struct.pack(
        "=8BI", family, 0, source.prefixlen, 0, 0, 0, 0, 1, 0
    )
    attributes = [
        (2, source.network_address.packed),  # FRA_SRC
        (6, struct.pack("=I", rule["priority"])),  # FRA_PRIORITY
        (15, struct.pack("=I", rule["route-table"])),  # FRA_TABLE
        (21, b"\x03"),  # FRA_PROTOCOL: RTPROT_BOOT
    ]
    if "fwmark" in rule:
        attributes.extend(
            [
                (10, struct.pack("=I", rule["fwmark"])),  # FRA_FWMARK
                (16, struct.pack("=I", rule["fwmask"])),  # FRA_FWMASK
            ]
        )
    for kind, value in attributes:
        payload += struct.pack("=HH", len(value) + 4, kind)
        payload += value + b"\0" * (-len(value) % 4)
    # RTM_NEWRULE with REQUEST | ACK | CREATE omits ip rule add's EXCL flag.
    message = (
        struct.pack("=IHHII", len(payload) + 16, 32, 0x405, 1, 0) + payload
    )
    with socket.socket(
        socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE
    ) as sock:
        sock.settimeout(5)
        sock.bind((0, 0))
        sock.sendto(message, (0, 0))
        reply = sock.recv(4096)
    assert struct.unpack_from("=H", reply, 4)[0] == 2, reply  # NLMSG_ERROR
    assert struct.unpack_from("=i", reply, 16)[0] == 0, reply


@contextmanager
def _external_rules(family, rules, extra_args=()):
    added = []
    try:
        for rule in rules:
            if rule in added:
                _add_duplicate_rule(rule)
            else:
                exec_cmd(
                    _ip_rule_command(family, "add", rule)
                    + ["protocol", "boot", *extra_args],
                    check=True,
                )
            added.append(rule)
        yield
    finally:
        for rule in added:
            for current in _kernel_rules(family):
                if (
                    str(ip_network(current["src"])) == rule["ip-from"]
                    and current["priority"] == rule["priority"]
                    and int(current["table"]) == rule["route-table"]
                ):
                    exec_cmd(_ip_rule_command(family, "del", rule))


def _profile_rules(family):
    uuid = exec_cmd(
        ["nmcli", "-g", "GENERAL.CON-UUID", "device", "show", "eth1"],
        check=True,
    )[1].strip()
    return exec_cmd(
        ["nmcli", "-g", f"{family}.routing-rules", "connection", "show", uuid],
        check=True,
    )[1].strip()


def _static_iface(family):
    address = (
        {"ip": "192.0.2.251", "prefix-length": 24}
        if family == "ipv4"
        else {"ip": "2001:db8:1::251", "prefix-length": 64}
    )
    ip_config = {"enabled": True, "dhcp": False, "address": [address]}
    if family == "ipv6":
        ip_config["autoconf"] = False
    return {"name": "eth1", "state": "up", family: ip_config}


@contextmanager
def _uncommitted_apply(desired, timeout):
    try:
        exec_cmd(
            ["nmstatectl", "apply", "--no-commit", "--timeout", str(timeout)],
            stdin=yaml.safe_dump(desired).encode(),
            check=True,
        )
        yield
    finally:
        exec_cmd(["nmstatectl", "rollback"])


def test_remove_external_route_rules(
    rule_family, nm_with_routing_rule_checkpoints
):
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18),
        _rule(rule_family, 20, UNRELATED_RULE_TABLE),
    ]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    with _external_rules(rule_family, rules):
        _assert_kernel_rules(rule_family, rules)
        for _ in range(2):
            libnmstate.apply(desired)
            _assert_kernel_rules(rule_family, [rules[2]])


def test_external_rules_unchanged_on_unsupported_nm(
    rule_family, nm_without_routing_rule_checkpoints
):
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18, UNRELATED_RULE_TABLE),
    ]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    with _external_rules(rule_family, rules):
        _assert_kernel_rules(rule_family, rules)
        original_rules = _kernel_rules(rule_family)
        with pytest.raises(NmstateVerificationError):
            libnmstate.apply(desired)
        assert _kernel_rules(rule_family) == original_rules


@pytest.mark.parametrize("priority", [RULE_PRIORITY, 0])
def test_remove_exact_external_route_rule(
    rule_family, priority, nm_with_routing_rule_checkpoints
):
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18),
        _rule(rule_family, 20, UNRELATED_RULE_TABLE),
    ]
    for rule in rules:
        rule["priority"] = priority
    desired = {"route-rules": {"config": [dict(rules[0], state="absent")]}}
    with _external_rules(rule_family, rules):
        _assert_kernel_rules(rule_family, rules)
        remaining_rules = [
            rule
            for rule in _kernel_rules(rule_family, include_defaults=True)
            if rule["src"] == "all"
            or str(ip_network(rule["src"])) != rules[0]["ip-from"]
        ]
        for _ in range(2):
            libnmstate.apply(desired)
            _assert_kernel_rules(rule_family, rules[1:])
            assert (
                _kernel_rules(rule_family, include_defaults=True)
                == remaining_rules
            )


def test_remove_zero_fwmark_external_route_rule(
    rule_family, nm_with_routing_rule_checkpoints
):
    selected = dict(_rule(rule_family, 16), fwmark=0, fwmask=255)
    survivor = dict(selected, fwmark=1)
    desired = {"route-rules": {"config": [dict(selected, state="absent")]}}
    with _external_rules(rule_family, [survivor, survivor, selected]):
        original_rules = _kernel_rules(rule_family, include_defaults=True)
        expected = [
            rule
            for rule in original_rules
            if "fwmark" not in rule or int(rule["fwmark"], 0) != 0
        ]
        assert len(original_rules) == len(expected) + 1
        assert sum(rule.get("fwmark") == "0x1" for rule in expected) == 2
        for _ in range(2):
            libnmstate.apply(desired)
            assert (
                _kernel_rules(rule_family, include_defaults=True) == expected
            )


def test_external_route_rules_preserve_tunnel_id(
    rule_family, nm_with_routing_rule_checkpoints
):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    desired = {"route-rules": {"config": [dict(selected, state="absent")]}}
    with _external_rules(rule_family, [survivor], ["tun_id", "0x100000001"]):
        expected = _kernel_rules(rule_family, include_defaults=True)
        assert any(rule.get("tun_id") == 0x100000001 for rule in expected)
        with _external_rules(rule_family, [selected]):
            _assert_kernel_rules(rule_family, [survivor, selected])
            for _ in range(2):
                libnmstate.apply(desired)
                assert (
                    _kernel_rules(rule_family, include_defaults=True)
                    == expected
                )


def test_external_route_rules_preserve_inverted_rule(
    rule_family, nm_with_routing_rule_checkpoints
):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    desired = {"route-rules": {"config": [dict(selected, state="absent")]}}
    extra_args = [
        "not",
        "tun_id",
        "0x100000001",
        "ipproto",
        "tcp",
        "sport",
        "1000-2000",
        "dport",
        "443",
        "uidrange",
        "1000-2000",
    ]
    with _external_rules(rule_family, [survivor], extra_args):
        expected = _kernel_rules(rule_family, include_defaults=True)
        inverted = next(rule for rule in expected if "not" in rule)
        assert inverted["tun_id"] == 0x100000001
        assert inverted["uid_start"] == 1000
        assert inverted["uid_end"] == 2000
        assert inverted["sport_start"] == 1000
        assert inverted["sport_end"] == 2000
        assert inverted["dport"] == 443
        with _external_rules(rule_family, [selected]):
            for _ in range(2):
                libnmstate.apply(desired)
                assert (
                    _kernel_rules(rule_family, include_defaults=True)
                    == expected
                )


@pytest.mark.parametrize("with_public_rule", [False, True])
def test_remove_external_route_rule_with_tunnel_id(
    rule_family, with_public_rule, nm_with_routing_rule_checkpoints
):
    selected = _rule(rule_family, 16)
    public_rules = [_rule(rule_family, 18)] if with_public_rule else []
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    with _external_rules(rule_family, [selected], ["tun_id", "0x100000001"]):
        with _external_rules(rule_family, public_rules):
            original = _kernel_rules(rule_family, include_defaults=True)
            assert any(rule.get("tun_id") == 0x100000001 for rule in original)
            expected = [
                rule
                for rule in original
                if str(rule.get("table")) != str(EXTERNAL_RULE_TABLE)
            ]
            for _ in range(2):
                libnmstate.apply(desired)
                assert (
                    _kernel_rules(rule_family, include_defaults=True)
                    == expected
                )


def test_remove_profile_route_rule_without_net_admin(
    rule_family, eth1_up, nm_with_routing_rule_checkpoints
):
    rule = _rule(rule_family, 16)
    libnmstate.apply(
        {
            "interfaces": [_static_iface(rule_family)],
            "route-rules": {"config": [rule]},
        }
    )
    _assert_kernel_rules(rule_family, [rule])
    desired = {"route-rules": {"config": [dict(rule, state="absent")]}}
    exec_cmd(
        ["setpriv", "--bounding-set=-net_admin", "nmstatectl", "apply"],
        stdin=yaml.safe_dump(desired).encode(),
        check=True,
    )
    assert not _kernel_rules(rule_family)
    assert not _profile_rules(rule_family)


@pytest.fixture
def eth1_alt_name(eth1_up):
    name = "nmstate-rule-test"
    yield name
    libnmstate.apply(
        {
            "interfaces": [
                {
                    "name": "eth1",
                    "alt-names": [{"name": name, "state": "absent"}],
                }
            ]
        }
    )


def test_external_route_rules_present_overrides_absent(
    rule_family, eth1_alt_name, nm_with_routing_rule_checkpoints
):
    kept = _rule(rule_family, 16)
    added = _rule(rule_family, 18)
    stale = _rule(rule_family, 20)
    external_unrelated = _rule(rule_family, 22, UNRELATED_RULE_TABLE)
    profile_unrelated = _rule(rule_family, 24, UNRELATED_RULE_TABLE)
    profile_stale = _rule(rule_family, 26)
    iface = _static_iface(rule_family)
    iface["alt-names"] = [{"name": eth1_alt_name}]
    libnmstate.apply(
        {
            "interfaces": [iface],
            "route-rules": {"config": [profile_unrelated, profile_stale]},
        }
    )
    original_profile_rules = _profile_rules(rule_family)
    unrelated_profile_rule = next(
        rule.strip()
        for rule in original_profile_rules.split(",")
        if f"table {UNRELATED_RULE_TABLE}" in rule
    )

    with _external_rules(rule_family, [kept, stale, external_unrelated]):
        assert _profile_rules(rule_family) == original_profile_rules
        _assert_kernel_rules(
            rule_family,
            [
                kept,
                stale,
                external_unrelated,
                profile_unrelated,
                profile_stale,
            ],
        )
        unrelated_kernel_rule = next(
            rule
            for rule in _kernel_rules(rule_family)
            if str(ip_network(rule["src"])) == external_unrelated["ip-from"]
        )
        desired = {
            "interfaces": [iface],
            "route-rules": {
                "config": [
                    kept,
                    added,
                    {"route-table": EXTERNAL_RULE_TABLE, "state": "absent"},
                ]
            },
        }
        for _ in range(2):
            libnmstate.apply(desired)
            _assert_kernel_rules(
                rule_family,
                [kept, added, external_unrelated, profile_unrelated],
            )
            current_profile_rules = _profile_rules(rule_family)
            assert unrelated_profile_rule in current_profile_rules
            assert len(current_profile_rules.split(",")) == 3
            assert unrelated_kernel_rule in _kernel_rules(rule_family)
            link = json.loads(
                exec_cmd(["ip", "-json", "link", "show", "eth1"], check=True)[
                    1
                ]
            )[0]
            assert eth1_alt_name in link["altnames"]


@pytest.mark.parametrize("rollback_method", ["explicit", "timeout"])
@pytest.mark.parametrize("priority", [RULE_PRIORITY, 0])
def test_external_route_rules_rollback(
    rule_family, rollback_method, priority, nm_with_routing_rule_checkpoints
):
    rules = [
        _rule(rule_family, 20, UNRELATED_RULE_TABLE),
        _rule(rule_family, 18),
        _rule(rule_family, 16),
        _rule(rule_family, 18),
        _rule(rule_family, 22, UNRELATED_RULE_TABLE),
    ]
    for rule in rules:
        rule["priority"] = priority
    remaining_rules = [
        rule for rule in rules if rule["route-table"] == UNRELATED_RULE_TABLE
    ]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    timeout = 10 if rollback_method == "timeout" else 60
    with _external_rules(rule_family, rules):
        _assert_kernel_rules(rule_family, rules)
        original_rules = _kernel_rules(rule_family, include_defaults=True)
        with _uncommitted_apply(desired, timeout):
            _assert_kernel_rules(rule_family, remaining_rules)
            if rollback_method == "explicit":
                exec_cmd(["nmstatectl", "rollback"], check=True)
            assert retry_till_true_or_timeout(
                timeout + 10,
                lambda: _kernel_rules(rule_family, include_defaults=True)
                == original_rules,
            )


def test_external_route_rule_rollback_ignores_ongoing_dhcp(
    rule_family, eth1_up, nm_with_routing_rule_checkpoints
):
    uuid = exec_cmd(
        ["nmcli", "-g", "GENERAL.CON-UUID", "device", "show", "eth1"],
        check=True,
    )[1].strip()
    exec_cmd(
        [
            "nmcli",
            "connection",
            "modify",
            uuid,
            "ipv4.method",
            "auto",
            "ipv4.addresses",
            "",
            "ipv4.dhcp-timeout",
            "600",
            "ipv6.method",
            "disabled",
            "ipv6.addresses",
            "",
        ],
        check=True,
    )
    exec_cmd(["nmcli", "--wait", "0", "connection", "up", uuid], check=True)
    device = exec_cmd(
        ["nmcli", "-g", "GENERAL.DBUS-PATH", "device", "show", "eth1"],
        check=True,
    )[1].strip()

    def active_connection():
        value = exec_cmd(
            [
                "busctl",
                "get-property",
                NM_DBUS_NAME,
                device,
                f"{NM_DBUS_NAME}.Device",
                "ActiveConnection",
            ],
            check=True,
        )[1]
        return json.loads(value.split(maxsplit=1)[1])

    connection = active_connection()

    def is_activating():
        return (
            exec_cmd(
                [
                    "busctl",
                    "get-property",
                    NM_DBUS_NAME,
                    connection,
                    f"{NM_DBUS_NAME}.Connection.Active",
                    "State",
                ],
                check=True,
            )[1].strip()
            == "u 1"
        )

    assert retry_till_true_or_timeout(5, is_activating)
    rule = _rule(rule_family, 16)
    desired = {"route-rules": {"config": [dict(rule, state="absent")]}}
    with _external_rules(rule_family, [rule]):
        original_rules = _kernel_rules(rule_family)
        with _uncommitted_apply(desired, 60):
            assert not _kernel_rules(rule_family)
            exec_cmd(["timeout", "15", "nmstatectl", "rollback"], check=True)
            assert _kernel_rules(rule_family) == original_rules
            assert active_connection() == connection
            assert is_activating()


def test_external_route_rules_commit(
    rule_family, nm_with_routing_rule_checkpoints
):
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18, UNRELATED_RULE_TABLE),
    ]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    timeout = 10
    with _external_rules(rule_family, rules):
        _assert_kernel_rules(rule_family, rules)
        with _uncommitted_apply(desired, timeout):
            _assert_kernel_rules(rule_family, [rules[1]])
            exec_cmd(["nmstatectl", "commit"], check=True)
            committed_rules = _kernel_rules(rule_family)
            assert not retry_till_true_or_timeout(
                timeout + 2,
                lambda: _kernel_rules(rule_family) != committed_rules,
            )
            _assert_kernel_rules(rule_family, [rules[1]])


def test_external_route_rule_rollback_preserves_raw_selectors(
    rule_family, nm_with_routing_rule_checkpoints
):
    rule = _rule(rule_family, 16)
    extra_args = [
        "ipproto",
        "tcp",
        "sport",
        "1000-2000",
        "dport",
        "443",
        "uidrange",
        "1000-2000",
    ]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    with _external_rules(rule_family, [rule], extra_args):
        original_rules = _kernel_rules(rule_family)
        assert len(original_rules) == 1
        for selector in (
            "ipproto",
            "sport_start",
            "sport_end",
            "dport",
            "uid_start",
            "uid_end",
        ):
            assert selector in original_rules[0], original_rules
        with _uncommitted_apply(desired, 60):
            assert not _kernel_rules(rule_family)
            exec_cmd(["nmstatectl", "rollback"], check=True)
            assert retry_till_true_or_timeout(
                15, lambda: _kernel_rules(rule_family) == original_rules
            )


def test_external_route_rule_rollback_preserves_later_rule(
    rule_family, nm_with_routing_rule_checkpoints
):
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18, UNRELATED_RULE_TABLE),
    ]
    later_rule = _rule(rule_family, 20, UNRELATED_RULE_TABLE)
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    with _external_rules(rule_family, rules):
        original_rules = _kernel_rules(rule_family)
        with _uncommitted_apply(desired, 60):
            _assert_kernel_rules(rule_family, [rules[1]])
            with _external_rules(rule_family, [later_rule]):
                later_kernel_rule = next(
                    rule
                    for rule in _kernel_rules(rule_family)
                    if str(ip_network(rule["src"])) == later_rule["ip-from"]
                )
                exec_cmd(["nmstatectl", "rollback"], check=True)
                assert retry_till_true_or_timeout(
                    15,
                    lambda: [
                        rule
                        for rule in _kernel_rules(rule_family)
                        if rule != later_kernel_rule
                    ]
                    == original_rules,
                )
                _assert_kernel_rules(rule_family, [*rules, later_rule])
                assert later_kernel_rule in _kernel_rules(rule_family)


@pytest.fixture
def cleanup_loopback():
    yield
    libnmstate.apply(
        yaml.load(
            """---
            interfaces:
            - name: lo
              type: loopback
              state: absent
            """,
            Loader=yaml.SafeLoader,
        )
    )


def test_store_route_table_local_rule_to_loopback(cleanup_loopback):
    libnmstate.apply(
        yaml.load(
            """---
            route-rules:
              config:
                - route-table: 255
                  priority: 12345
                  family: ipv4
                - route-table: 255
                  priority: 12346
                  family: ipv6
            """,
            Loader=yaml.SafeLoader,
        )
    )

    assert (
        exec_cmd("nmcli -g ipv4.routing-rules c show lo".split())[1].strip()
        == "priority 12345 from 0.0.0.0/0 table 255"
    )

    assert (
        exec_cmd("nmcli -g ipv6.routing-rules c show lo".split())[1].strip()
        == r"priority 12346 from \:\:/0 table 255"
    )
