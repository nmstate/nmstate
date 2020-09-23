#
# Copyright (c) 2019 Red Hat, Inc.
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
from libnmstate.error import NmstateValueError
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .testlib import iprule

IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ROUTE_TABLE_ID1 = 50
IPV4_ROUTE_TABLE_ID2 = 51

IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ROUTE_TABLE_ID1 = 50
IPV6_ROUTE_TABLE_ID2 = 51

IPV4_DNS_NAMESERVER = "8.8.8.8"
IPV6_DNS_NAMESERVER = "2001:4860:4860::8888"
DNS_SEARCHES = ["example.org", "example.com"]


ETH1_INTERFACE_STATE = {
    Interface.NAME: "eth1",
    Interface.STATE: InterfaceState.UP,
    Interface.TYPE: InterfaceType.ETHERNET,
    Interface.IPV4: {
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
        InterfaceIPv4.DHCP: False,
        InterfaceIPv4.ENABLED: True,
    },
    Interface.IPV6: {
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        ],
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.AUTOCONF: False,
        InterfaceIPv6.ENABLED: True,
    },
}


@pytest.mark.tier1
def test_add_static_routes(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


@pytest.mark.tier1
def test_add_gateway(eth1_up):
    routes = [_get_ipv4_gateways()[0], _get_ipv6_test_routes()[0]]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def test_add_route_without_metric(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    for route in routes:
        del route[Route.METRIC]

    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def test_add_route_without_table_id(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    for route in routes:
        del route[Route.TABLE_ID]

    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def test_multiple_gateway(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: _get_ipv4_gateways() + _get_ipv6_gateways()
            },
        }
    )


@pytest.mark.tier1
def test_change_gateway(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    _get_ipv4_gateways()[0],
                    _get_ipv6_gateways()[0],
                ]
            },
        }
    )

    routes = [_get_ipv4_gateways()[1], _get_ipv6_gateways()[1]]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.STATE: Route.STATE_ABSENT,
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.DESTINATION: "0.0.0.0/0",
                    },
                    {
                        Route.STATE: Route.STATE_ABSENT,
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.DESTINATION: "::/0",
                    },
                ]
                + routes
            },
        }
    )

    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def _assert_routes(routes, state):
    """
    Assuming we are all operating eth1 routes
    """
    routes = copy.deepcopy(routes)
    for route in routes:
        if Route.METRIC not in route:
            route[Route.METRIC] = Route.USE_DEFAULT_METRIC
        if Route.TABLE_ID not in route:
            route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE
    routes.sort(key=_route_sort_key)
    config_routes = []
    for config_route in state[Route.KEY][Route.CONFIG]:
        if config_route[Route.NEXT_HOP_INTERFACE] == "eth1":
            config_routes.append(config_route)

    config_routes.sort(key=_route_sort_key)
    assert routes == config_routes

    # The running routes contains more route entries than desired config
    # The running routes also has different metric and table id for
    # USE_DEFAULT_ROUTE_TABLE and USE_DEFAULT_METRIC
    running_routes = state[Route.KEY][Route.RUNNING]
    for route in routes:
        _assert_in_running_route(route, running_routes)


def _assert_in_running_route(route, running_routes):
    route_in_running_routes = False
    for running_route in running_routes:
        metric = route.get(Route.METRIC, Route.USE_DEFAULT_METRIC)
        table_id = route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE)
        if metric == Route.USE_DEFAULT_METRIC:
            running_route = copy.deepcopy(running_route)
            running_route[Route.METRIC] = Route.USE_DEFAULT_METRIC
        if table_id == Route.USE_DEFAULT_ROUTE_TABLE:
            running_route = copy.deepcopy(running_route)
            running_route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE

        if route == running_route:
            route_in_running_routes = True
            break
    assert route_in_running_routes


def _get_ipv4_test_routes():
    return [
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: IPV4_ROUTE_TABLE_ID1,
        },
        {
            Route.DESTINATION: "203.0.113.0/24",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: IPV4_ROUTE_TABLE_ID2,
        },
    ]


def _get_ipv4_gateways():
    return [
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: "192.0.2.2",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
    ]


def _get_ipv6_test_routes():
    return [
        {
            Route.DESTINATION: "2001:db8:a::/64",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::a",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: IPV6_ROUTE_TABLE_ID1,
        },
        {
            Route.DESTINATION: "2001:db8:b::/64",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::b",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: IPV6_ROUTE_TABLE_ID2,
        },
    ]


def _get_ipv6_gateways():
    return [
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::f",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::e",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
    ]


def _route_sort_key(route):
    return (
        route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
        route.get(Route.NEXT_HOP_INTERFACE, ""),
        route.get(Route.DESTINATION, ""),
    )


parametrize_ip_ver_routes = pytest.mark.parametrize(
    "get_routes_func",
    [(_get_ipv4_test_routes), (_get_ipv6_test_routes)],
    ids=["ipv4", "ipv6"],
)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_remove_specific_route(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)

    absent_route = routes[0]
    absent_route[Route.STATE] = Route.STATE_ABSENT
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: [absent_route]},
        }
    )

    expected_routes = routes[1:]

    cur_state = libnmstate.show()
    _assert_routes(expected_routes, cur_state)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_remove_wildcast_route_with_iface(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)

    absent_route = {
        Route.STATE: Route.STATE_ABSENT,
        Route.NEXT_HOP_INTERFACE: "eth1",
    }
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: [absent_route]},
        }
    )

    expected_routes = []

    cur_state = libnmstate.show()
    _assert_routes(expected_routes, cur_state)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_remove_wildcast_route_without_iface(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)

    absent_routes = []
    for route in routes:
        absent_routes.append(
            {
                Route.STATE: Route.STATE_ABSENT,
                Route.DESTINATION: route[Route.DESTINATION],
            }
        )
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: absent_routes},
        }
    )

    expected_routes = []

    cur_state = libnmstate.show()
    _assert_routes(expected_routes, cur_state)


# TODO: Once we can disable IPv6, we should add an IPv6 test case here
def test_disable_ipv4_with_routes_in_current(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: _get_ipv4_test_routes()},
        }
    )

    eth1_state = copy.deepcopy(ETH1_INTERFACE_STATE)
    eth1_state[Interface.IPV4] = {InterfaceIPv4.ENABLED: False}

    libnmstate.apply({Interface.KEY: [eth1_state]})

    cur_state = libnmstate.show()
    _assert_routes([], cur_state)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_iface_down_with_routes_in_current(eth1_up, get_routes_func):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: get_routes_func()},
        }
    )

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.DOWN,
                }
            ]
        }
    )

    cur_state = libnmstate.show()
    _assert_routes([], cur_state)


@pytest.fixture(scope="function")
def eth1_static_gateway_dns(eth1_up):
    routes = (
        [_get_ipv4_gateways()[0], _get_ipv6_gateways()[0]]
        + _get_ipv4_test_routes()
        + _get_ipv6_test_routes()
    )

    state = {
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {Route.CONFIG: routes},
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: [IPV6_DNS_NAMESERVER, IPV4_DNS_NAMESERVER],
                DNS.SEARCH: DNS_SEARCHES,
            }
        },
    }

    libnmstate.apply(state)
    yield state
    # Remove DNS config
    libnmstate.apply(
        {Interface.KEY: [], DNS.KEY: {DNS.CONFIG: {}}}, verify_change=False
    )


@pytest.mark.tier1
@pytest.mark.xfail(
    raises=AssertionError,
    reason="https://bugzilla.redhat.com/1748389",
    strict=True,
)
def test_apply_empty_state_preserve_routes(eth1_static_gateway_dns):
    state = eth1_static_gateway_dns

    libnmstate.apply({Interface.KEY: []})

    current_state = libnmstate.show()

    assert (
        current_state[Route.KEY][Route.CONFIG]
        == state[Route.KEY][Route.CONFIG]
    )
    assert current_state[DNS.KEY][DNS.CONFIG] == state[DNS.KEY][DNS.CONFIG]


@pytest.fixture(scope="function")
def route_rule_test_env(eth1_static_gateway_dns):
    yield eth1_static_gateway_dns
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: []},
            RouteRule.KEY: {RouteRule.CONFIG: []},
            DNS.KEY: {DNS.CONFIG: {}},
        },
        verify_change=False,
    )


@pytest.mark.tier1
def test_route_rule_add_without_from_or_to(route_rule_test_env):
    state = route_rule_test_env
    state[RouteRule.KEY] = {
        RouteRule.CONFIG: [
            {RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1},
            {RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1},
        ]
    }

    with pytest.raises(NmstateValueError):
        libnmstate.apply(state)


@pytest.mark.tier1
def test_route_rule_add_from_only(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add_to_only(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.PRIORITY: 1000,
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.PRIORITY: 1000,
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add_without_priority(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_add_without_route_table(route_rule_test_env):
    """
    When route table is not define in route rule, the main route table will
    be used.
    """
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.PRIORITY: 1000,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.PRIORITY: 1000,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_add_from_to_single_host(route_rule_test_env):
    """
    When route table is not define in route rule, the main route table will
    be used.
    """
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::",
            RouteRule.IP_TO: "2001:db8:f::/64",
        },
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::",
        },
        {RouteRule.IP_FROM: "203.0.113.1", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_add_with_auto_route_table_id(eth1_up):
    state = eth1_up
    rules = [
        {RouteRule.IP_FROM: "192.168.3.2/32", RouteRule.ROUTE_TABLE: 200},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    ipv4_state = state[Interface.KEY][0][Interface.IPV4]
    ipv4_state[InterfaceIPv4.ENABLED] = True
    ipv4_state[InterfaceIPv4.DHCP] = True
    ipv4_state[InterfaceIPv4.AUTO_ROUTE_TABLE_ID] = 200

    libnmstate.apply(state)
    _check_ip_rules(rules)


def _check_ip_rules(rules):
    for rule in rules:
        iprule.ip_rule_exist_in_os(
            rule.get(RouteRule.IP_FROM),
            rule.get(RouteRule.IP_TO),
            rule.get(RouteRule.PRIORITY),
            rule.get(RouteRule.ROUTE_TABLE),
        )
