# SPDX-License-Identifier: Apache-2.0

import json
from contextlib import contextmanager
from ipaddress import ip_network

import libnmstate
from libnmstate.error import NmstateNotSupportedError
from libnmstate.error import NmstateVerificationError
import pytest
import yaml

from ..testlib.cmdlib import exec_cmd
from ..testlib.retry import retry_till_true_or_timeout

EXTERNAL_RULE_TABLE = 500
UNRELATED_RULE_TABLE = 501
RULE_PRIORITY = 100


@pytest.fixture(params=["ipv4", "ipv6"])
def rule_family(request):
    return request.param


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
    return [
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


@contextmanager
def _external_rules(family, rules, protocol="boot", extra_args=()):
    added = []
    selectors = (
        ["protocol", protocol] if protocol is not None else []
    ) + list(extra_args)
    try:
        for rule in rules:
            exec_cmd(
                _ip_rule_command(family, "add", rule) + selectors,
                check=True,
            )
            added.append(rule)
        yield
    finally:
        for rule in reversed(added):
            exec_cmd(_ip_rule_command(family, "del", rule) + selectors)


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


def _rules_match(family, expected):
    return sorted(
        (str(ip_network(rule["src"])), rule["priority"], int(rule["table"]))
        for rule in _kernel_rules(family)
    ) == sorted(
        (rule["ip-from"], rule["priority"], rule["route-table"])
        for rule in expected
    )


def _absent_rules(*rules):
    return {
        "route-rules": {
            "config": [dict(rule, state="absent") for rule in rules]
        }
    }


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


def _profile_rules(family):
    return exec_cmd(
        [
            "nmcli",
            "-g",
            f"{family}.routing-rules",
            "connection",
            "show",
            "eth1",
        ],
        check=True,
    )[1].strip()


def _set_profile_rules(family, rules, reapply=True):
    exec_cmd(
        [
            "nmcli",
            "connection",
            "modify",
            "eth1",
            f"{family}.routing-rules",
            ", ".join(rules),
        ],
        check=True,
    )
    if reapply:
        exec_cmd(["nmcli", "device", "reapply", "eth1"], check=True)


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


@pytest.mark.parametrize("verify_change", [True, False])
def test_remove_external_rules_preserves_other_table(
    rule_family,
    verify_change,
):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 16, UNRELATED_RULE_TABLE)
    desired = _absent_rules({"route-table": EXTERNAL_RULE_TABLE})
    with _external_rules(rule_family, [survivor]):
        expected = _kernel_rules(rule_family)
        with _external_rules(rule_family, [selected]):
            for _ in range(2):
                libnmstate.apply(desired, verify_change=verify_change)
                assert _kernel_rules(rule_family) == expected


def test_remove_exact_external_rule_at_priority_zero(rule_family):
    selected = dict(_rule(rule_family, 16), priority=0)
    survivor = dict(_rule(rule_family, 18), priority=0)
    with _external_rules(rule_family, [survivor]):
        expected = _kernel_rules(rule_family, include_defaults=True)
        with _external_rules(rule_family, [selected]):
            libnmstate.apply(_absent_rules(selected))
            assert (
                _kernel_rules(rule_family, include_defaults=True) == expected
            )


def test_remove_external_rule_preserves_dynamic_twin(rule_family):
    rule = _rule(rule_family, 16)
    with _external_rules(rule_family, [rule], protocol="keepalived"):
        expected = _kernel_rules(rule_family)
        with _external_rules(rule_family, [rule], protocol="static"):
            libnmstate.apply(_absent_rules(rule))
            assert _kernel_rules(rule_family) == expected


def test_remove_external_rule_without_protocol(rule_family):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    with _external_rules(rule_family, [survivor], protocol=None):
        expected = _kernel_rules(rule_family)
        with _external_rules(rule_family, [selected], protocol=None):
            libnmstate.apply(_absent_rules(selected))
            assert _kernel_rules(rule_family) == expected


@pytest.mark.parametrize("dynamic_neighbor", [False, True])
def test_adopt_external_present_rule(rule_family, dynamic_neighbor, eth1_up):
    present = dict(_rule(rule_family, 16), iif="eth1")
    dynamic = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    libnmstate.apply({"interfaces": [_static_iface(rule_family)]})
    assert not _profile_rules(rule_family)
    with _external_rules(
        rule_family,
        [dynamic] if dynamic_neighbor else [],
        protocol="keepalived",
    ):
        with _external_rules(
            rule_family, [present], extra_args=["iif", "eth1"]
        ):
            libnmstate.apply({"route-rules": {"config": [present]}})
            profile = _profile_rules(rule_family).replace(r"\:", ":")
            address = ip_network(present["ip-from"]).network_address
            assert f"from {address} " in profile
            assert f"table {EXTERNAL_RULE_TABLE}" in profile
            assert "iif eth1" in profile
            assert str(UNRELATED_RULE_TABLE) not in profile


@pytest.mark.parametrize("neighbor_kind", ["dynamic", "inverted"])
def test_auto_priority_reserves_preserved_external_rule(
    rule_family, neighbor_kind, eth1_up
):
    neighbor = dict(_rule(rule_family, 16), priority=30005)
    desired_rule = dict(_rule(rule_family, 18), iif="eth1")
    desired_rule.pop("priority")
    libnmstate.apply({"interfaces": [_static_iface(rule_family)]})
    with _external_rules(
        rule_family,
        [neighbor],
        protocol="keepalived" if neighbor_kind == "dynamic" else "boot",
        extra_args=["not"] if neighbor_kind == "inverted" else [],
    ):
        before = _kernel_rules(rule_family)
        libnmstate.apply({"route-rules": {"config": [desired_rule]}})
        rules = _kernel_rules(rule_family)
        assert all(rule in rules for rule in before)
        added = [
            rule
            for rule in rules
            if str(ip_network(rule["src"])) == desired_rule["ip-from"]
        ]
        assert len(added) == 1
        assert added[0]["priority"] == 30006
        assert "priority 30006 " in _profile_rules(rule_family)


def test_cli_diff_excludes_preserved_inverted_rule(rule_family):
    inverted = _rule(rule_family, 16)
    selected = _rule(rule_family, 18)
    desired = _absent_rules({"route-table": EXTERNAL_RULE_TABLE})
    with _external_rules(rule_family, [inverted], extra_args=["not"]):
        expected = _kernel_rules(rule_family)
        output = exec_cmd(
            ["nmstatectl", "apply"],
            stdin=yaml.safe_dump(desired).encode(),
            check=True,
        )[1]
        diff = yaml.safe_load(output) or {}
        assert not diff.get("route-rules", {}).get("config")
        assert _kernel_rules(rule_family) == expected
        with _external_rules(rule_family, [selected]):
            output = exec_cmd(
                ["nmstatectl", "apply"],
                stdin=yaml.safe_dump(desired).encode(),
                check=True,
            )[1]
            diff = yaml.safe_load(output)
            assert diff["route-rules"]["config"] == [
                dict(selected, state="absent")
            ]
            assert _kernel_rules(rule_family) == expected


def test_ambiguous_unspec_rule_rolls_back_profile_changes(
    rule_family, eth1_up
):
    external = _rule(rule_family, 16)
    profile = dict(_rule(rule_family, 18, UNRELATED_RULE_TABLE), iif="eth1")
    replacement = dict(
        _rule(rule_family, 20, UNRELATED_RULE_TABLE), iif="eth1"
    )
    libnmstate.apply(
        {
            "interfaces": [_static_iface(rule_family)],
            "route-rules": {"config": [profile]},
        }
    )
    expected_profile = _profile_rules(rule_family)
    with _external_rules(rule_family, [external], protocol=None):
        with _external_rules(rule_family, [external], protocol="keepalived"):
            expected_kernel = sorted(
                json.dumps(rule, sort_keys=True)
                for rule in _kernel_rules(rule_family)
            )
            desired = _absent_rules(external, profile)
            desired["route-rules"]["config"].append(replacement)
            with pytest.raises(NmstateNotSupportedError):
                libnmstate.apply(desired)
            assert retry_till_true_or_timeout(
                10,
                lambda: _profile_rules(rule_family) == expected_profile
                and sorted(
                    json.dumps(rule, sort_keys=True)
                    for rule in _kernel_rules(rule_family)
                )
                == expected_kernel,
            )


def test_ambiguous_external_rule_rejects_whole_batch(rule_family):
    broad = _rule(rule_family, 16)
    broad["ip-from"] = "0.0.0.0/0" if rule_family == "ipv4" else "::/0"
    inverted = _rule(rule_family, 16)
    unambiguous = dict(_rule(rule_family, 18), priority=RULE_PRIORITY - 1)
    with _external_rules(rule_family, [broad, unambiguous]):
        with _external_rules(rule_family, [inverted], extra_args=["not"]):
            before = _kernel_rules(rule_family)
            with pytest.raises(NmstateNotSupportedError):
                libnmstate.apply(
                    _absent_rules({"route-table": EXTERNAL_RULE_TABLE})
                )
            assert _kernel_rules(rule_family) == before


def test_external_rule_on_ignored_interface_is_preserved(rule_family, eth1_up):
    ignored = _rule(rule_family, 16)
    selected = _rule(rule_family, 18)
    desired = _absent_rules({"route-table": EXTERNAL_RULE_TABLE})
    desired["interfaces"] = [{"name": "eth1", "state": "ignore"}]
    with _external_rules(rule_family, [ignored], extra_args=["iif", "eth1"]):
        expected = _kernel_rules(rule_family)
        with _external_rules(rule_family, [selected]):
            libnmstate.apply(desired)
            assert _kernel_rules(rule_family) == expected


def test_external_rule_present_overrides_absent(rule_family, eth1_up):
    kept = _rule(rule_family, 16)
    added = _rule(rule_family, 18)
    stale = _rule(rule_family, 20)
    survivor = _rule(rule_family, 22, UNRELATED_RULE_TABLE)
    desired = {
        "interfaces": [_static_iface(rule_family)],
        "route-rules": {
            "config": [
                kept,
                added,
                {"route-table": EXTERNAL_RULE_TABLE, "state": "absent"},
            ]
        },
    }
    expected = {
        (rule["ip-from"], rule["priority"], rule["route-table"])
        for rule in [kept, added, survivor]
    }
    with _external_rules(rule_family, [kept, survivor]):
        preserved = _kernel_rules(rule_family)
        with _external_rules(rule_family, [stale]):
            for _ in range(2):
                libnmstate.apply(desired)
                rules = _kernel_rules(rule_family)
                assert all(rule in rules for rule in preserved)
                assert {
                    (
                        str(ip_network(rule["src"])),
                        rule["priority"],
                        int(rule["table"]),
                    )
                    for rule in rules
                } == expected


def test_remove_external_rule_preserves_from_all_profile(rule_family, eth1_up):
    selected = _rule(rule_family, 16)
    profile = {
        "family": rule_family,
        "priority": RULE_PRIORITY,
        "route-table": EXTERNAL_RULE_TABLE,
    }
    libnmstate.apply(
        {
            "interfaces": [_static_iface(rule_family)],
            "route-rules": {"config": [profile]},
        }
    )
    expected = _kernel_rules(rule_family)
    assert len(expected) == 1
    with _external_rules(rule_family, [selected]):
        libnmstate.apply(_absent_rules(selected))
        assert _kernel_rules(rule_family) == expected


@pytest.mark.parametrize("remove_profile_rule", [False, True])
def test_remove_external_rule_preserves_inverted_profile(
    rule_family, remove_profile_rule, eth1_up
):
    selected = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    removed = _rule(rule_family, 20)
    profile_rules = [
        f"priority {RULE_PRIORITY} not from {selected['ip-from']} "
        f"table {EXTERNAL_RULE_TABLE}",
        f"priority {RULE_PRIORITY} from {survivor['ip-from']} "
        f"table {UNRELATED_RULE_TABLE}",
    ]
    libnmstate.apply({"interfaces": [_static_iface(rule_family)]})
    _set_profile_rules(rule_family, profile_rules)
    expected_kernel = _kernel_rules(rule_family)
    expected_profile = _profile_rules(rule_family)
    assert len(expected_kernel) == 2
    assert any("not" in rule for rule in expected_kernel)
    assert " not " in expected_profile

    absent = [selected]
    if remove_profile_rule:
        _set_profile_rules(
            rule_family,
            profile_rules
            + [
                f"priority {RULE_PRIORITY} from {removed['ip-from']} "
                f"table {EXTERNAL_RULE_TABLE}"
            ],
        )
        absent.append(removed)

    with _external_rules(rule_family, [selected]):
        for _ in range(2):
            libnmstate.apply(_absent_rules(*absent))
            assert _kernel_rules(rule_family) == expected_kernel
            assert _profile_rules(rule_family) == expected_profile


def test_remove_external_rule_preserves_applied_inverted_rule(
    rule_family, eth1_up
):
    selected = _rule(rule_family, 16)
    removed = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    libnmstate.apply({"interfaces": [_static_iface(rule_family)]})
    original_profile = _profile_rules(rule_family)
    exec_cmd(
        [
            "nmcli",
            "device",
            "modify",
            "eth1",
            f"{rule_family}.routing-rules",
            f"priority {RULE_PRIORITY} not from {selected['ip-from']} "
            f"table {EXTERNAL_RULE_TABLE}, "
            f"priority {RULE_PRIORITY} from {removed['ip-from']} "
            f"table {UNRELATED_RULE_TABLE}",
        ],
        check=True,
    )
    applied_kernel = _kernel_rules(rule_family)
    assert len(applied_kernel) == 2
    expected_kernel = [rule for rule in applied_kernel if "not" in rule]
    assert len(expected_kernel) == 1
    assert _profile_rules(rule_family) == original_profile
    with _external_rules(rule_family, [selected]):
        for _ in range(2):
            libnmstate.apply(_absent_rules(selected, removed))
            assert _kernel_rules(rule_family) == expected_kernel
            assert " not " in _profile_rules(rule_family)


def test_remove_profile_rule_does_not_restore_inactive_inverted_rule(
    rule_family, eth1_up
):
    inverted = _rule(rule_family, 16)
    survivor = _rule(rule_family, 18, UNRELATED_RULE_TABLE)
    removed = _rule(rule_family, 20)
    survivor_setting = (
        f"priority {RULE_PRIORITY} from {survivor['ip-from']} "
        f"table {UNRELATED_RULE_TABLE}"
    )
    removed_setting = (
        f"priority {RULE_PRIORITY} from {removed['ip-from']} "
        f"table {EXTERNAL_RULE_TABLE}"
    )
    libnmstate.apply({"interfaces": [_static_iface(rule_family)]})
    _set_profile_rules(rule_family, [survivor_setting])
    expected_kernel = _kernel_rules(rule_family)
    expected_profile = _profile_rules(rule_family)
    assert len(expected_kernel) == 1
    _set_profile_rules(
        rule_family,
        [
            f"priority {RULE_PRIORITY} not from {inverted['ip-from']} "
            f"table {EXTERNAL_RULE_TABLE}",
            survivor_setting,
            removed_setting,
        ],
    )
    exec_cmd(
        [
            "nmcli",
            "device",
            "modify",
            "eth1",
            f"{rule_family}.routing-rules",
            ", ".join([survivor_setting, removed_setting]),
        ],
        check=True,
    )
    applied_kernel = _kernel_rules(rule_family)
    assert len(applied_kernel) == 2
    assert all("not" not in rule for rule in applied_kernel)
    assert " not " in _profile_rules(rule_family)
    for _ in range(2):
        libnmstate.apply(_absent_rules(removed))
        assert _kernel_rules(rule_family) == expected_kernel
        assert _profile_rules(rule_family) == expected_profile


@pytest.mark.parametrize("saved_inverted_host", [16, 18])
def test_mtu_change_preserves_saved_only_rule_edits(
    rule_family, saved_inverted_host, eth1_up
):
    applied_inverted = _rule(rule_family, 16)
    saved_inverted = _rule(rule_family, saved_inverted_host)
    applied_ordinary = _rule(rule_family, 20, UNRELATED_RULE_TABLE)
    saved_ordinary = _rule(rule_family, 22, UNRELATED_RULE_TABLE)
    iface = dict(_static_iface(rule_family), mtu=1500)
    libnmstate.apply({"interfaces": [iface]})
    _set_profile_rules(
        rule_family,
        [
            f"priority {RULE_PRIORITY} not from {applied_inverted['ip-from']} "
            f"table {EXTERNAL_RULE_TABLE}",
            f"priority {RULE_PRIORITY} from {applied_ordinary['ip-from']} "
            f"table {UNRELATED_RULE_TABLE}",
        ],
    )
    applied_kernel = _kernel_rules(rule_family)
    _set_profile_rules(
        rule_family,
        [
            f"priority {RULE_PRIORITY} not from {saved_inverted['ip-from']} "
            f"table {EXTERNAL_RULE_TABLE}",
            f"priority {RULE_PRIORITY} from {saved_ordinary['ip-from']} "
            f"table {UNRELATED_RULE_TABLE}",
        ],
        reapply=False,
    )
    expected_profile = _profile_rules(rule_family)
    assert _kernel_rules(rule_family) == applied_kernel
    libnmstate.apply({"interfaces": [{"name": "eth1", "mtu": 1400}]})
    assert _profile_rules(rule_family) == expected_profile


@pytest.mark.parametrize("completion", ["explicit", "timeout"])
def test_rollback_restores_profile_rule_but_not_external_rule(
    rule_family, completion, eth1_up
):
    external = _rule(rule_family, 16)
    profile = _rule(rule_family, 18)
    survivor = _rule(rule_family, 20, UNRELATED_RULE_TABLE)
    libnmstate.apply(
        {
            "interfaces": [_static_iface(rule_family)],
            "route-rules": {"config": [profile]},
        }
    )
    assert _rules_match(rule_family, [profile])
    with _external_rules(rule_family, [external, survivor]):
        timeout = 10 if completion == "timeout" else 60
        with _uncommitted_apply(
            _absent_rules({"route-table": EXTERNAL_RULE_TABLE}), timeout
        ):
            assert _rules_match(rule_family, [survivor])
            if completion == "explicit":
                libnmstate.rollback()
            assert retry_till_true_or_timeout(
                timeout + 10,
                _rules_match,
                rule_family,
                [profile, survivor],
            )


def test_verification_failure_does_not_restore_external_rule(eth1_up):
    selected = _rule("ipv4", 16)
    survivor = _rule("ipv4", 18, UNRELATED_RULE_TABLE)
    desired = _absent_rules(selected)
    desired.update(
        {
            "interfaces": [
                {
                    "name": "eth1",
                    "state": "up",
                    "ipv4": {"dhcp": True, "enabled": True},
                }
            ],
            "routes": {
                "config": [
                    {
                        "destination": "203.0.113.0/24",
                        "next-hop-address": "192.0.2.251",
                        "next-hop-interface": "eth1",
                    }
                ]
            },
        }
    )
    with _external_rules("ipv4", [selected, survivor]):
        with pytest.raises(NmstateVerificationError):
            libnmstate.apply(desired)
        assert _rules_match("ipv4", [survivor])


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
