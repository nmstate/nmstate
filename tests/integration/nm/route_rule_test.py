# SPDX-License-Identifier: Apache-2.0

import json
import shlex
import socket
import stat
import struct
import subprocess
from contextlib import contextmanager
from ipaddress import ip_network
from pathlib import Path

import libnmstate
from libnmstate.error import NmstateDependencyError
import pytest
import yaml

from ..testlib.cmdlib import exec_cmd
from ..testlib.retry import retry_till_true_or_timeout

EXTERNAL_RULE_TABLE = 500
UNRELATED_RULE_TABLE = 501
RULE_PRIORITY = 100
NM_DBUS_NAME = "org.freedesktop.NetworkManager"
NM_DBUS_PATH = "/org/freedesktop/NetworkManager"
ROLLBACK_SERVICE = "nmstate-rollback.service"
ROLLBACK_SOCKET = Path("/run/nmstate/rollback/control.sock")


@pytest.fixture(params=["ipv4", "ipv6"])
def rule_family(request):
    return request.param


def _rollback_helper_ready():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect(str(ROLLBACK_SOCKET))
        except OSError:
            return False
    return True


def _rollback_helper_pid():
    return int(
        exec_cmd(
            [
                "systemctl",
                "show",
                "--property=MainPID",
                "--value",
                ROLLBACK_SERVICE,
            ],
            check=True,
        )[1].strip()
    )


@pytest.fixture
def rollback_helper_available():
    rc, state, _ = exec_cmd(
        [
            "systemctl",
            "show",
            "--property=LoadState",
            "--value",
            ROLLBACK_SERVICE,
        ]
    )
    if rc != 0 or state.strip() != "loaded":
        pytest.skip("nmstate rollback service is not installed or available")
    exec_cmd(["systemctl", "start", ROLLBACK_SERVICE], check=True)
    assert retry_till_true_or_timeout(10, _rollback_helper_ready)
    socket_stat = ROLLBACK_SOCKET.stat()
    assert socket_stat.st_uid == 0
    assert stat.S_IMODE(socket_stat.st_mode) == 0o600
    assert stat.S_IMODE(ROLLBACK_SOCKET.parent.stat().st_mode) == 0o711


@pytest.fixture
def rollback_helper_unavailable(rollback_helper_available):
    exec_cmd(
        ["systemctl", "mask", "--runtime", "--now", ROLLBACK_SERVICE],
        check=True,
    )
    try:
        yield
    finally:
        exec_cmd(
            ["systemctl", "unmask", "--runtime", ROLLBACK_SERVICE], check=True
        )
        exec_cmd(["systemctl", "start", ROLLBACK_SERVICE], check=True)
        assert retry_till_true_or_timeout(10, _rollback_helper_ready)


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


def test_remove_external_route_rules(rule_family, rollback_helper_available):
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


def test_external_route_rules_preserve_dynamic_protocols(
    rule_family, rollback_helper_available
):
    protocols = [
        "boot",
        "static",
        "unspec",
        "dhcp",
        "ra",
        "keepalived",
        "babel",
        "17",
        "bgp",
    ]
    rules = [_rule(rule_family, host) for host in range(16, 25)]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    try:
        for rule, protocol in zip(rules, protocols):
            exec_cmd(
                _ip_rule_command(rule_family, "add", rule)
                + ["protocol", protocol],
                check=True,
            )
        original = _kernel_rules(rule_family, include_defaults=True)
        expected = [
            rule
            for rule in original
            if str(rule.get("table")) != str(EXTERNAL_RULE_TABLE)
            or rule.get("protocol", "unspec") not in protocols[:3]
        ]
        assert len(original) - len(expected) == 3
        assert len(_kernel_rules(rule_family)) == len(protocols)
        for _ in range(2):
            libnmstate.apply(desired)
            assert (
                _kernel_rules(rule_family, include_defaults=True) == expected
            )
    finally:
        for rule in rules:
            exec_cmd(_ip_rule_command(rule_family, "del", rule))


def test_external_rules_unchanged_without_rollback_helper(
    rule_family, rollback_helper_unavailable
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
        with pytest.raises(
            NmstateDependencyError, match="(?i)rollback|helper|service"
        ):
            libnmstate.apply(desired)
        assert _kernel_rules(rule_family) == original_rules


@pytest.mark.parametrize("priority", [RULE_PRIORITY, 0])
def test_remove_exact_external_route_rule(
    rule_family, priority, rollback_helper_available
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
    rule_family, rollback_helper_available
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
    rule_family, rollback_helper_available
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
    rule_family, rollback_helper_available
):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18)
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
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
    rule_family, with_public_rule, rollback_helper_available
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


@pytest.mark.parametrize("with_external_rule", [False, True])
def test_remove_route_rules_without_net_admin(
    rule_family, with_external_rule, eth1_up, rollback_helper_unavailable
):
    rule = _rule(rule_family, 16)
    libnmstate.apply(
        {
            "interfaces": [_static_iface(rule_family)],
            "route-rules": {"config": [rule]},
        }
    )
    _assert_kernel_rules(rule_family, [rule])
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    external_rules = [_rule(rule_family, 18)] if with_external_rule else []
    checkpoints_command = [
        "busctl",
        "get-property",
        NM_DBUS_NAME,
        NM_DBUS_PATH,
        NM_DBUS_NAME,
        "Checkpoints",
    ]
    original_checkpoints = exec_cmd(checkpoints_command, check=True)[1]
    original_profile_rules = _profile_rules(rule_family)
    with _external_rules(rule_family, external_rules):
        original_rules = _kernel_rules(rule_family, include_defaults=True)
        rc, stdout, stderr = exec_cmd(
            ["setpriv", "--bounding-set=-net_admin", "nmstatectl", "apply"],
            stdin=yaml.safe_dump(desired).encode(),
        )
        if with_external_rule:
            assert rc != 0
            assert "requires CAP_NET_ADMIN" in stdout + stderr
            assert (
                _kernel_rules(rule_family, include_defaults=True)
                == original_rules
            )
            assert _profile_rules(rule_family) == original_profile_rules
        else:
            assert rc == 0, (stdout, stderr)
            assert not _kernel_rules(rule_family)
            assert not _profile_rules(rule_family)
        assert (
            exec_cmd(checkpoints_command, check=True)[1]
            == original_checkpoints
        )
        assert not (ROLLBACK_SOCKET.parent / "transaction.json").exists()


@pytest.mark.parametrize(
    "prefix,error",
    [
        (
            ["setpriv", "--bounding-set=-sys_admin"],
            "effective capabilities",
        ),
        (["unshare", "--uts"], "same UTS namespace"),
        (["unshare", "--mount"], "same mount namespace"),
        (
            ["env", "NMSTATE_NM_DISPATCH_DIR=/run/nmstate-test-dispatch"],
            "same dispatcher directory",
        ),
    ],
)
def test_external_rule_apply_rejects_different_execution_context(
    rule_family, prefix, error, eth1_alt_name, rollback_helper_available
):
    selected = _rule(rule_family, 16)
    iface = _static_iface(rule_family)
    iface["alt-names"] = [{"name": eth1_alt_name}]
    original_hostname = socket.gethostname()
    alt_name_file = Path("/etc/systemd/network/98-nmstate-eth1.link")
    original_file = (
        alt_name_file.read_bytes() if alt_name_file.exists() else None
    )
    checkpoints_command = [
        "busctl",
        "get-property",
        NM_DBUS_NAME,
        NM_DBUS_PATH,
        NM_DBUS_NAME,
        "Checkpoints",
    ]
    original_checkpoints = exec_cmd(checkpoints_command, check=True)[1]
    desired = {
        "hostname": {"running": "nmstate-delegation-denied"},
        "interfaces": [iface],
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        },
    }
    with _external_rules(rule_family, [selected]):
        original_rules = _kernel_rules(rule_family, include_defaults=True)
        try:
            rc, stdout, stderr = exec_cmd(
                prefix + ["nmstatectl", "apply"],
                stdin=yaml.safe_dump(desired).encode(),
            )
            assert rc != 0
            assert error in stdout + stderr
            assert socket.gethostname() == original_hostname
            assert (
                alt_name_file.read_bytes() if alt_name_file.exists() else None
            ) == original_file
            assert (
                _kernel_rules(rule_family, include_defaults=True)
                == original_rules
            )
            assert (
                exec_cmd(checkpoints_command, check=True)[1]
                == original_checkpoints
            )
            assert not (ROLLBACK_SOCKET.parent / "transaction.json").exists()
        finally:
            socket.sethostname(original_hostname)


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
    rule_family, eth1_alt_name, rollback_helper_available
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
    rule_family, rollback_method, priority, rollback_helper_available
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


def test_external_route_rule_unsettled_rollback_requires_recovery(
    rule_family, rollback_helper_available
):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    journal = ROLLBACK_SOCKET.parent / "transaction.json"
    with _external_rules(rule_family, [selected, survivor]):
        with _uncommitted_apply(desired, 60):
            try:
                exec_cmd(["systemctl", "stop", ROLLBACK_SERVICE], check=True)
                record = json.loads(journal.read_text())
                checkpoint = record["checkpoint"]
                # Inject a baseline connection that cannot settle after NM
                # consumes the checkpoint. Only edit with the helper stopped.
                record["connections"]["connections"].append(
                    [
                        "00000000-0000-0000-0000-000000000001",
                        "nmstate-missing",
                        2,
                    ]
                )
                journal.write_text(json.dumps(record))
                exec_cmd(["systemctl", "start", ROLLBACK_SERVICE], check=True)
                assert retry_till_true_or_timeout(10, _rollback_helper_ready)
                result = subprocess.run(
                    ["nmstatectl", "rollback", checkpoint],
                    capture_output=True,
                    text=True,
                    timeout=40,
                )
                assert result.returncode != 0, result
                assert "requires explicit recovery" in (
                    result.stdout + result.stderr
                )
                record = json.loads(journal.read_text())
                assert "unresolved" in record["phase"], record
                assert record["nm_finished"] is False
                assert record["rules"]
                assert all(
                    step["restoration"] is None and not step["restored"]
                    for step in record["rules"]
                )
                _assert_kernel_rules(rule_family, [survivor])
                checkpoints = exec_cmd(
                    [
                        "busctl",
                        "get-property",
                        NM_DBUS_NAME,
                        NM_DBUS_PATH,
                        NM_DBUS_NAME,
                        "Checkpoints",
                    ],
                    check=True,
                )[1]
                assert checkpoint not in checkpoints
                unresolved = journal.read_bytes()
                for restart in (False, True):
                    if restart:
                        exec_cmd(
                            ["systemctl", "restart", ROLLBACK_SERVICE],
                            check=True,
                        )
                        assert retry_till_true_or_timeout(
                            10, _rollback_helper_ready
                        )
                    result = subprocess.run(
                        ["nmstatectl", "rollback", checkpoint],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    assert result.returncode != 0, result
                    assert "requires explicit recovery" in (
                        result.stdout + result.stderr
                    )
                    assert journal.read_bytes() == unresolved
                    _assert_kernel_rules(rule_family, [survivor])
                assert not retry_till_true_or_timeout(
                    3, lambda: journal.read_bytes() != unresolved
                )
                _assert_kernel_rules(rule_family, [survivor])
            finally:
                exec_cmd(["systemctl", "stop", ROLLBACK_SERVICE], check=True)
                # The transaction only removed the rules owned by this test.
                journal.unlink(missing_ok=True)
                exec_cmd(["systemctl", "start", ROLLBACK_SERVICE], check=True)
                assert retry_till_true_or_timeout(10, _rollback_helper_ready)


def test_external_route_rule_rollback_ignores_ongoing_dhcp(
    rule_family, eth1_up, rollback_helper_available
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

    connection = "/"

    def is_activating():
        if connection == "/":
            return False
        rc, state, _ = exec_cmd(
            [
                "busctl",
                "get-property",
                NM_DBUS_NAME,
                connection,
                f"{NM_DBUS_NAME}.Connection.Active",
                "State",
            ]
        )
        return rc == 0 and state.strip() == "u 1"

    def find_activating_connection():
        nonlocal connection
        connection = active_connection()
        return is_activating()

    assert retry_till_true_or_timeout(5, find_activating_connection)
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


def test_external_route_rules_commit(rule_family, rollback_helper_available):
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


@pytest.mark.parametrize("completion", ["commit", "rollback", "timeout"])
def test_external_route_rules_survive_helper_restart(
    rule_family, completion, rollback_helper_available
):
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18, UNRELATED_RULE_TABLE),
        _rule(rule_family, 16),
    ]
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    timeout = 10
    with _external_rules(rule_family, rules):
        original = _kernel_rules(rule_family, include_defaults=True)
        with _uncommitted_apply(desired, timeout):
            _assert_kernel_rules(rule_family, [rules[1]])
            checkpoints = shlex.split(
                exec_cmd(
                    [
                        "busctl",
                        "get-property",
                        NM_DBUS_NAME,
                        NM_DBUS_PATH,
                        NM_DBUS_NAME,
                        "Checkpoints",
                    ],
                    check=True,
                )[1]
            )[2:]
            assert len(checkpoints) == 1, checkpoints
            assert (
                exec_cmd(
                    [
                        "busctl",
                        "get-property",
                        NM_DBUS_NAME,
                        checkpoints[0],
                        f"{NM_DBUS_NAME}.Checkpoint",
                        "RollbackTimeout",
                    ],
                    check=True,
                )[1].strip()
                == "u 0"
            )
            old_pid = _rollback_helper_pid()
            assert old_pid > 0
            exec_cmd(
                [
                    "systemctl",
                    "kill",
                    "--kill-who=main",
                    "--signal=KILL",
                    ROLLBACK_SERVICE,
                ],
                check=True,
            )
            assert retry_till_true_or_timeout(
                10,
                lambda: _rollback_helper_pid() not in (0, old_pid)
                and _rollback_helper_ready(),
            )
            if completion != "timeout":
                exec_cmd(
                    ["nmstatectl", completion, checkpoints[0]], check=True
                )
            if completion == "commit":
                _assert_kernel_rules(rule_family, [rules[1]])
                committed = _kernel_rules(rule_family, include_defaults=True)
                assert not retry_till_true_or_timeout(
                    timeout + 2,
                    lambda: _kernel_rules(rule_family, include_defaults=True)
                    != committed,
                )
            else:
                assert retry_till_true_or_timeout(
                    timeout + 10,
                    lambda: _kernel_rules(rule_family, include_defaults=True)
                    == original,
                )


@pytest.fixture
def blocked_eth1_pre_down(eth1_up, tmp_path):
    libnmstate.apply({"interfaces": [_static_iface("ipv4")]})
    entered = tmp_path / "pre-down-entered"
    released = tmp_path / "pre-down-released"
    script = Path(
        "/etc/NetworkManager/dispatcher.d/pre-down.d/"
        "90-nmstate-rule-rollback-test"
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    with script.open("x") as stream:
        stream.write(
            '#!/bin/sh\nif [ "$1" = eth1 ] && [ "$2" = pre-down ]; then\n'
            f"    : > {shlex.quote(str(entered))}\n"
            "    remaining=300\n"
            f"    while [ ! -e {shlex.quote(str(released))} ] "
            '&& [ "$remaining" -gt 0 ]; do\n'
            "        sleep 0.1\n"
            "        remaining=$((remaining - 1))\n"
            "    done\nfi\n"
        )
    script.chmod(0o755)
    try:
        yield entered, released
    finally:
        released.touch()
        script.unlink()


def test_external_route_rules_rollback_waits_for_deactivation(
    rule_family, rollback_helper_available, blocked_eth1_pre_down
):
    entered, released = blocked_eth1_pre_down
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18, UNRELATED_RULE_TABLE),
        _rule(rule_family, 16),
    ]
    desired = {
        "interfaces": [{"name": "eth1", "state": "down"}],
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        },
    }
    checkpoint_command = [
        "busctl",
        "get-property",
        NM_DBUS_NAME,
        NM_DBUS_PATH,
        NM_DBUS_NAME,
        "Checkpoints",
    ]
    with _external_rules(rule_family, rules):
        original = _kernel_rules(rule_family, include_defaults=True)
        original_ipv4 = next(
            iface["ipv4"]
            for iface in libnmstate.show()["interfaces"]
            if iface["name"] == "eth1"
        )
        with _uncommitted_apply(desired, 60):
            assert retry_till_true_or_timeout(15, entered.exists)
            _assert_kernel_rules(rule_family, [rules[1]])
            checkpoint = exec_cmd(checkpoint_command, check=True)[1]
            assert shlex.split(checkpoint)[1] == "1", checkpoint
            process = subprocess.Popen(
                ["nmstatectl", "rollback"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                assert not retry_till_true_or_timeout(
                    2, lambda: process.poll() is not None
                )
                assert (
                    exec_cmd(checkpoint_command, check=True)[1] == checkpoint
                )
                released.touch()
                stdout, stderr = process.communicate(timeout=30)
                assert process.returncode == 0, (stdout, stderr)
                assert (
                    _kernel_rules(rule_family, include_defaults=True)
                    == original
                )
                iface = next(
                    iface
                    for iface in libnmstate.show()["interfaces"]
                    if iface["name"] == "eth1"
                )
                assert iface["state"] == "up"
                assert iface["ipv4"] == original_ipv4
            finally:
                released.touch()
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)


@pytest.mark.parametrize("killed_process", ["caller", "helper"])
def test_external_route_rules_recover_interrupted_apply(
    rule_family,
    killed_process,
    rollback_helper_available,
    blocked_eth1_pre_down,
    tmp_path,
):
    entered, released = blocked_eth1_pre_down
    rules = [
        _rule(rule_family, 16),
        _rule(rule_family, 18, UNRELATED_RULE_TABLE),
        _rule(rule_family, 16),
    ]
    desired = {
        "interfaces": [
            {
                "name": "eth1",
                "state": "up",
                "ipv4": {
                    "enabled": True,
                    "dhcp": True,
                    "address": [],
                    "auto-route-table-id": 502,
                },
            }
        ],
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        },
    }
    desired_file = tmp_path / "desired.yml"
    desired_file.write_text(yaml.safe_dump(desired))
    with _external_rules(rule_family, rules):
        original = _kernel_rules(rule_family, include_defaults=True)
        original_ipv4 = next(
            iface["ipv4"]
            for iface in libnmstate.show()["interfaces"]
            if iface["name"] == "eth1"
        )
        uuid = exec_cmd(
            ["nmcli", "-g", "GENERAL.CON-UUID", "device", "show", "eth1"],
            check=True,
        )[1].strip()
        profile_command = [
            "nmcli",
            "-g",
            "ipv4.method,ipv4.addresses,ipv4.route-table",
            "connection",
            "show",
            uuid,
        ]
        original_profile = exec_cmd(profile_command, check=True)[1]
        process = subprocess.Popen(
            [
                "nmstatectl",
                "apply",
                "--no-commit",
                "--timeout",
                "60",
                str(desired_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            assert retry_till_true_or_timeout(15, entered.exists)
            _assert_kernel_rules(rule_family, [rules[1]])
            assert process.poll() is None
            if killed_process == "caller":
                process.kill()
            else:
                exec_cmd(
                    [
                        "systemctl",
                        "kill",
                        "--kill-who=main",
                        "--signal=KILL",
                        ROLLBACK_SERVICE,
                    ],
                    check=True,
                )
            released.touch()
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode != 0, (stdout, stderr)
            assert retry_till_true_or_timeout(
                30,
                lambda: _kernel_rules(rule_family, include_defaults=True)
                == original,
            )
            assert retry_till_true_or_timeout(10, _rollback_helper_ready)
            state = libnmstate.show()
            iface = next(
                iface
                for iface in state["interfaces"]
                if iface["name"] == "eth1"
            )
            assert iface["state"] == "up"
            assert iface["ipv4"] == original_ipv4
            assert exec_cmd(profile_command, check=True)[1] == original_profile
            assert (
                exec_cmd(
                    [
                        "nmcli",
                        "-g",
                        "GENERAL.CON-UUID",
                        "device",
                        "show",
                        "eth1",
                    ],
                    check=True,
                )[1].strip()
                == uuid
            )
        finally:
            released.touch()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
            exec_cmd(["nmstatectl", "rollback"])


def test_external_route_rule_rollback_preserves_raw_selectors(
    rule_family, rollback_helper_available
):
    rule = _rule(rule_family, 16)
    extra_args = [
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
    desired = {
        "route-rules": {
            "config": [{"route-table": EXTERNAL_RULE_TABLE, "state": "absent"}]
        }
    }
    with _external_rules(rule_family, [rule], extra_args):
        original_rules = _kernel_rules(rule_family)
        assert len(original_rules) == 1
        assert original_rules[0]["tun_id"] == 0x100000001
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
    rule_family, rollback_helper_available
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
