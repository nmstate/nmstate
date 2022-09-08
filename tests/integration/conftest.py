#
# Copyright (c) 2018-2020 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

import logging
import os
import subprocess
import warnings

import pytest

import libnmstate
from libnmstate.schema import DNS
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .testlib import ifacelib


REPORT_HEADER = """RPMs: {rpms}
OS: {osname}
nmstate: {nmstate_version}
"""


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark time consuming test")
    config.addinivalue_line("markers", "tier2")
    config.addinivalue_line("markers", "tier1")


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--runslow"):
        # --runslow is not in cli: skip slow tests
        _mark_skip_slow_tests(items)
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
    _ethx_init()
    yield
    restore_old_state(old_state)
    _diff_initial_state(old_state)


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
        }
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
def eth1_up():
    with ifacelib.iface_up("eth1") as ifstate:
        yield ifstate


@pytest.fixture(scope="function")
def eth2_up():
    with ifacelib.iface_up("eth2") as ifstate:
        yield ifstate


port0_up = eth1_up
port1_up = eth2_up


def _diff_initial_state(old_state):
    new_state = libnmstate.show()
    new_state = _remove_interfaces_from_env(new_state)

    if old_state != new_state:
        warnings.warn(
            "Network state after test run does not match network state "
            "before test run:\n {}\n".format(
                libnmstate.prettystate.format_desired_current_state_diff(
                    old_state, new_state
                )
            )
        )


def pytest_report_header(config):
    return REPORT_HEADER.format(
        rpms=_get_package_nvr("NetworkManager"),
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
    return (
        subprocess.check_output(["rpm", "-q", package]).strip().decode("utf-8")
    )


def _get_osname():
    with open("/etc/os-release") as os_release:
        for line in os_release.readlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", maxsplit=1)[1].strip().strip('"')
    return ""


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
