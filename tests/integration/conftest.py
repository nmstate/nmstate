# SPDX-License-Identifier: LGPL-2.1-or-later

import logging
import os
import subprocess
import tempfile

from pathlib import Path

import pytest

import libnmstate
from libnmstate.schema import Description
from libnmstate.schema import DNS
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .testlib import ifacelib
from .testlib.veth import create_veth_pair
from .testlib.veth import remove_veth_pair


REPORT_HEADER = """RPMs: {rpms}
OS: {osname}
nmstate: {nmstate_version}
"""

ISOLATE_NAMESPACE = "nmstate_test_ep"
LIBNMSTATE_APPLY = libnmstate.apply
LIBNMSTATE_SHOW = libnmstate.show
DUMP_STATES_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), ".states"
)
# Dump YAMLs for AI training
OPT_DUMP_AI_TRAIN_YAML = "--dump-ai-train-yaml"
DUMP_AI_TRAIN_YAML = False


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark time consuming test")
    config.addinivalue_line("markers", "tier2")
    config.addinivalue_line("markers", "tier1")


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--dump-states",
        action="store_true",
        default=False,
        help="dump applied and showed network states",
    )
    parser.addoption(
        OPT_DUMP_AI_TRAIN_YAML,
        action="store_true",
        default=False,
        help="dump applied network states with top description only",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--runslow"):
        # --runslow is not in cli: skip slow tests
        _mark_skip_slow_tests(items)

    if config.getoption(OPT_DUMP_AI_TRAIN_YAML):
        global DUMP_AI_TRAIN_YAML
        DUMP_AI_TRAIN_YAML = True

    if config.getoption("--dump-states") or config.getoption(
        OPT_DUMP_AI_TRAIN_YAML
    ):
        libnmstate.apply = _custom_apply_with_dump_state
        libnmstate.show = _custom_show_with_dump_state

    _mark_tier2_tests(items)


def _mark_skip_slow_tests(items):
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


def _mark_tier2_tests(items):
    for item in items:
        if "tier1" not in item.keywords:
            item.add_marker(pytest.mark.tier2)


@pytest.fixture(scope="session", autouse=True)
def test_env_setup():
    _logging_setup()
    old_state = libnmstate.show()
    old_state = _remove_interfaces_from_env(old_state)
    _remove_dns_route_route_rule()
    for nic_name in ["eth1", "eth2"]:
        remove_veth_pair(nic_name, ISOLATE_NAMESPACE)
    for nic_name in ["eth1", "eth2"]:
        create_veth_pair(nic_name, f"{nic_name}.ep", ISOLATE_NAMESPACE)
    _ethx_init()
    yield
    for nic_name in ["eth1", "eth2"]:
        remove_veth_pair(nic_name, ISOLATE_NAMESPACE)
    restore_old_state(old_state)


def _remove_dns_route_route_rule():
    """
    Remove existing DNS, routes, route rules in case it interference tests.
    """
    libnmstate.apply(
        {
            DNS.KEY: {DNS.CONFIG: {}},
            Route.KEY: {
                Route.CONFIG: [{Route.STATE: Route.STATE_ABSENT}],
            },
            RouteRule.KEY: {RouteRule.CONFIG: []},
        },
        verify_change=False,
    )


def _logging_setup():
    logging.basicConfig(
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
    )


def _ethx_init():
    """Remove any existing definitions on the ethX interfaces."""
    ifacelib.ifaces_init("eth1", "eth2")


def _remove_interfaces_from_env(state):
    """
    Remove references from interfaces passed to environment variable
    NMSTATE_TEST_IGNORE_IFACE.
    """
    ignore_iface = os.getenv("NMSTATE_TEST_IGNORE_IFACE")
    if ignore_iface is None:
        return state

    state["interfaces"] = [
        i for i in state["interfaces"] if ignore_iface not in i["name"]
    ]
    state["routes"]["config"] = [
        r
        for r in state["routes"]["config"]
        if ignore_iface not in r["next-hop-interface"]
    ]
    return state


@pytest.fixture(scope="function")
def eth1_up(test_env_setup):
    with ifacelib.iface_up("eth1") as ifstate:
        yield ifstate


@pytest.fixture(scope="function")
def eth2_up(test_env_setup):
    with ifacelib.iface_up("eth2") as ifstate:
        yield ifstate


port0_up = eth1_up
port1_up = eth2_up


def pytest_report_header(config):
    nm_ver = _get_package_nvr("NetworkManager")
    try:
        nm_libreswan_ver = _get_package_nvr("NetworkManager-libreswan")
    except subprocess.CalledProcessError:
        nm_libreswan_ver = "NetworkManager-libreswan (not installed)"
    return REPORT_HEADER.format(
        rpms=f"{nm_ver} {nm_libreswan_ver}",
        osname=_get_osname(),
        nmstate_version=_get_nmstate_version(),
    )


def _get_nmstate_version():
    """
    Prefer RPM version of nmstate, if not found, use libnmstate module version
    """
    try:
        return _get_package_nvr("nmstate")
    except subprocess.CalledProcessError:
        return libnmstate.__version__


def _get_package_nvr(package):
    return subprocess.check_output(
        ["rpm", "-q", "--qf", "%{name}-%{VERSION}-%{RELEASE}", package]
    ).decode("utf-8")


def _get_osname():
    with open("/etc/os-release") as os_release:
        for line in os_release.readlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", maxsplit=1)[1].strip().strip('"')
    return ""


def _dump_state(
    state,
):
    path = Path(DUMP_STATES_DIR)
    path.mkdir(exist_ok=True)
    test_name = (
        os.environ.get("PYTEST_CURRENT_TEST")
        .split(":")[-1]
        .split(" ")[0]
        .lower()
    )
    state_file = tempfile.NamedTemporaryFile(
        dir=path, prefix=test_name + "-", suffix=".yml", delete=False
    )
    with open(state_file.name, "a") as outfile:
        outfile.write(libnmstate.PrettyState(state).yaml)


def _custom_apply_with_dump_state(
    desired_state,
    *args,
    **kwargs,
):
    if DUMP_AI_TRAIN_YAML:
        cur_state = libnmstate.show()
    result = LIBNMSTATE_APPLY(
        desired_state,
        *args,
        **kwargs,
    )
    if DUMP_AI_TRAIN_YAML:
        if Description.KEY in desired_state:
            diff_state = libnmstate.generate_differences(
                desired_state, cur_state
            )
            _dump_state(diff_state)
    else:
        _dump_state(desired_state)
    return result


def _custom_show_with_dump_state(
    *args,
    **kwargs,
):
    current_state = LIBNMSTATE_SHOW(
        *args,
        **kwargs,
    )
    if not DUMP_AI_TRAIN_YAML:
        _dump_state(current_state)
    return current_state


# Only restore the interface with IPv4/IPv6 gateway with IP/DNS config only
# For test machine, it is expected to lose configurations
def restore_old_state(old_state):
    gw_routes = [
        rt
        for rt in old_state["routes"].get("config", [])
        if rt["destination"] in ("0.0.0.0/0", "::/0")
    ]
    gw_ifaces = [rt["next-hop-interface"] for rt in gw_routes]
    desire_state = {
        "interfaces": [],
        "routes": {"config": gw_routes},
        "dns-resolver": old_state.get("dns-resolver", {}),
    }
    for iface_name in gw_ifaces:
        for iface in old_state["interfaces"]:
            if iface["name"] in gw_ifaces:
                if iface["state"] == "up":
                    desire_state["interfaces"].append(
                        {
                            "name": iface["name"],
                            "type": iface["type"],
                            "ipv4": iface["ipv4"],
                            "ipv6": iface["ipv6"],
                        }
                    )
    if len(desire_state["interfaces"]):
        libnmstate.apply(desire_state, verify_change=False)
