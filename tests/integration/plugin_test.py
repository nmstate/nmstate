#
# Copyright (c) 2020 Red Hat, Inc.
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

import copy

import pytest

import libnmstate
from libnmstate.error import NmstateDependencyError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import DNS
from libnmstate.schema import Route
from libnmstate.schema import RouteRule
from libnmstate.plugin import NmstatePlugin

from .testlib import statelib
from .testlib.servicelib import disable_service
from .testlib.plugin import tmp_plugin_dir


FOO_IFACE_NAME = "foo1"
FOO_IFACE_STATES = [
    {
        Interface.NAME: FOO_IFACE_NAME,
        Interface.TYPE: InterfaceType.OTHER,
        Interface.STATE: InterfaceState.UP,
        "foo": {"a": 1, "b": 2},
    }
]

BAR_IFACE_NAME = "bar1"
BAR_IFACE_STATES = [
    {
        Interface.NAME: BAR_IFACE_NAME,
        Interface.TYPE: InterfaceType.OTHER,
        Interface.STATE: InterfaceState.UP,
        "foo": {"a": 2},
    },
    {
        Interface.NAME: FOO_IFACE_NAME,
        Interface.TYPE: InterfaceType.OTHER,
        Interface.STATE: InterfaceState.UP,
        "foo": {"a": 3},
    },
]

TEST_ROUTE_ENTRY = {
    Route.DESTINATION: "198.51.100.0/24",
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: "192.0.2.1",
    Route.NEXT_HOP_INTERFACE: FOO_IFACE_NAME,
    Route.TABLE_ID: 100,
}

TEST_ROUTE_STATE = {
    Route.RUNNING: [TEST_ROUTE_ENTRY],
    Route.CONFIG: [],
}

TEST_DNS_STATE = {
    DNS.RUNNING: {
        DNS.SERVER: ["2001:4860:4860::8888", "1.1.1.1"],
        DNS.SEARCH: ["example.org", "example.com"],
    },
    DNS.CONFIG: [],
}

TEST_ROUTE_RULE_STATE = {
    RouteRule.CONFIG: [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.PRIORITY: 1000,
            RouteRule.ROUTE_TABLE: 100,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.PRIORITY: 1001,
            RouteRule.ROUTE_TABLE: 101,
        },
    ]
}

GET_IFACES_FORMAT = """
    def get_interfaces(self):
        return {ifaces}
"""

GET_ROUTES_FORMAT = """
    def get_routes(self):
        return {routes}
"""

GET_ROUTE_RULES_FORMAT = """
    def get_route_rules(self):
        return {route_rules}
"""

GET_DNS_FORMAT = """
    def get_dns_client_config(self):
        return {dns_config}
"""

LO_IFACE_INFO = {
    Interface.NAME: "lo",
    Interface.TYPE: InterfaceType.UNKNOWN,
    Interface.STATE: InterfaceState.UP,
    Interface.IPV4: {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: "127.0.0.1",
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 8,
            }
        ],
    },
    Interface.IPV6: {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: "::1",
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 128,
            }
        ],
    },
    Interface.MAC: "00:00:00:00:00:00",
    Interface.MTU: 65536,
}


@pytest.fixture
def with_foo_plugin():
    with tmp_plugin_dir() as plugin_dir:
        _gen_plugin_foo(plugin_dir)
        yield


@pytest.fixture
def with_multiple_plugins():
    with tmp_plugin_dir() as plugin_dir:
        _gen_plugin_foo(plugin_dir)
        _gen_plugin_bar(plugin_dir)
        yield


@pytest.fixture
def with_route_plugin():
    with tmp_plugin_dir() as plugin_dir:
        _gen_plugin_route_foo(plugin_dir)
        yield


@pytest.fixture
def with_route_rule_plugin():
    with tmp_plugin_dir() as plugin_dir:
        _gen_plugin_route_rule_foo(plugin_dir)
        yield


@pytest.fixture
def with_dns_plugin():
    with tmp_plugin_dir() as plugin_dir:
        _gen_plugin_dns_foo(plugin_dir)
        yield


def _gen_plugin(
    plugin_dir,
    plugin_name,
    plugin_class,
    priority,
    ifaces=None,
    routes=None,
    dns_config=None,
    route_rules=None,
):
    plugin_capabilities = []
    get_funs_txt = ""
    if ifaces:
        plugin_capabilities.append(NmstatePlugin.PLUGIN_CAPABILITY_IFACE)
        get_funs_txt += GET_IFACES_FORMAT.format(ifaces=f"{ifaces}")
    if routes:
        plugin_capabilities.append(NmstatePlugin.PLUGIN_CAPABILITY_ROUTE)
        get_funs_txt += GET_ROUTES_FORMAT.format(routes=f"{routes}")
    if route_rules:
        plugin_capabilities.append(NmstatePlugin.PLUGIN_CAPABILITY_ROUTE_RULE)
        get_funs_txt += GET_ROUTE_RULES_FORMAT.format(
            route_rules=f"{route_rules}"
        )
    if dns_config:
        plugin_capabilities.append(NmstatePlugin.PLUGIN_CAPABILITY_DNS)
        get_funs_txt += GET_DNS_FORMAT.format(dns_config=f"{dns_config}")

    plugin_txt = f"""
from libnmstate.plugin import NmstatePlugin
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

class {plugin_class}(NmstatePlugin):
    @property
    def name(self):
        return "{plugin_name}"

    @property
    def priority(self):
        return {priority}

    @property
    def plugin_capabilities(self):
        return {plugin_capabilities}

{get_funs_txt}

NMSTATE_PLUGIN = {plugin_class}
"""
    with open(f"{plugin_dir}/nmstate_plugin_{plugin_name}.py", "w") as fd:
        fd.write(plugin_txt)


def _gen_plugin_foo(plugin_dir):
    _gen_plugin(
        plugin_dir,
        "foo",
        "NmstateFooPlugin",
        NmstatePlugin.DEFAULT_PRIORITY + 1,
        ifaces=FOO_IFACE_STATES,
    )


def _gen_plugin_bar(plugin_dir):
    _gen_plugin(
        plugin_dir,
        "bar",
        "NmstateBarPlugin",
        NmstatePlugin.DEFAULT_PRIORITY + 2,
        ifaces=BAR_IFACE_STATES,
    )


def _gen_plugin_route_foo(plugin_dir):
    _gen_plugin(
        plugin_dir,
        "route_foo",
        "NmstateRouteFooPlugin",
        NmstatePlugin.DEFAULT_PRIORITY + 1,
        routes=TEST_ROUTE_STATE,
    )


def _gen_plugin_dns_foo(plugin_dir):
    _gen_plugin(
        plugin_dir,
        "dns_foo",
        "NmstateDnsFooPlugin",
        NmstatePlugin.DEFAULT_PRIORITY + 1,
        dns_config=TEST_DNS_STATE,
    )


def _gen_plugin_route_rule_foo(plugin_dir):
    _gen_plugin(
        plugin_dir,
        "route_rule_foo",
        "NmstateRouteRuleFooPlugin",
        NmstatePlugin.DEFAULT_PRIORITY + 1,
        route_rules=TEST_ROUTE_RULE_STATE,
    )


def test_load_foo_plugin(with_foo_plugin):
    current_state = statelib.show_only((FOO_IFACE_NAME,))
    assert current_state[Interface.KEY] == FOO_IFACE_STATES


def test_two_plugins_with_merged_iface_by_priority(with_multiple_plugins):
    current_state = statelib.show_only((BAR_IFACE_NAME, FOO_IFACE_NAME))
    expected_ifaces = copy.deepcopy(BAR_IFACE_STATES)
    expected_ifaces[1]["foo"]["b"] = 2
    assert current_state[Interface.KEY] == expected_ifaces


def test_load_external_route_plugin(with_route_plugin):
    state = libnmstate.show()
    assert TEST_ROUTE_ENTRY in state[Route.KEY][Route.RUNNING]


def test_load_external_route_rule_plugin(with_route_rule_plugin):
    state = libnmstate.show()
    assert state[RouteRule.KEY] == TEST_ROUTE_RULE_STATE


def test_load_external_dns_plugin(with_dns_plugin):
    state = libnmstate.show()
    assert state[DNS.KEY] == TEST_DNS_STATE


@pytest.fixture
def stop_nm_service():
    with disable_service("NetworkManager"):
        yield


def test_network_manager_plugin_with_daemon_stopped(stop_nm_service):
    with pytest.raises(NmstateDependencyError):
        from libnmstate.nm import NetworkManagerPlugin

        NetworkManagerPlugin().context

    state = statelib.show_only(("lo",))
    assert state[Interface.KEY][0] == LO_IFACE_INFO
