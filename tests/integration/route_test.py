#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
import copy

import pytest

import libnmstate
from libnmstate.error import NmstateNotImplementedError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route

IPV4_ADDRESS1 = '192.0.2.251'

IPV6_ADDRESS1 = '2001:db8:1::1'

ETH1_INTERFACE_STATE = {
    Interface.NAME: 'eth1',
    Interface.STATE: InterfaceState.UP,
    Interface.TYPE: InterfaceType.ETHERNET,
    Interface.IPV4: {
        'address': [
            {
                'ip': IPV4_ADDRESS1,
                'prefix-length': 24
            }
        ],
        'dhcp': False,
        'enabled': True
    },
    Interface.IPV6: {
        'address': [
            {
                'ip': IPV6_ADDRESS1,
                'prefix-length': 64
            }
        ],
        'dhcp': False,
        'autoconf': False,
        'enabled': True
    }
}


def test_add_static_routes(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def test_add_gateway(eth1_up):
    routes = [_get_ipv4_gateways()[0], _get_ipv6_test_routes()[0]]
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def test_add_route_without_metric(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    for route in routes:
        del route[Route.METRIC]

    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        }
    })

    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


def test_add_route_without_table_id(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    for route in routes:
        del route[Route.TABLE_ID]

    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        },
    })

    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)


@pytest.mark.xfail(raises=NmstateNotImplementedError,
                   reason="Red Hat Bug 1707396")
def test_multiple_gateway(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: _get_ipv4_gateways() + _get_ipv6_gateways()
            }
        })


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
        if config_route[Route.NEXT_HOP_INTERFACE] == 'eth1':
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
            Route.DESTINATION: '198.51.100.0/24',
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 50
        },
        {
            Route.DESTINATION: '203.0.113.0/24',
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 51
        }
    ]


def _get_ipv4_gateways():
    return [
        {
            Route.DESTINATION: '0.0.0.0/0',
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 254
        },
        {
            Route.DESTINATION: '0.0.0.0/0',
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: '192.0.2.2',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 254
        }
    ]


def _get_ipv6_test_routes():
    return [
        {
            Route.DESTINATION: '2001:db8:a::/64',
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: '2001:db8:1::a',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 50
        },
        {
            Route.DESTINATION: '2001:db8:b::/64',
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: '2001:db8:1::b',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 50
        }
    ]


def _get_ipv6_gateways():
    return [
        {
            Route.DESTINATION: '::/0',
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: '2001:db8:1::f',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 254
        },
        {
            Route.DESTINATION: '::/0',
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: '2001:db8:1::e',
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.TABLE_ID: 254
        }
    ]


def _route_sort_key(route):
    return (route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
            route.get(Route.NEXT_HOP_INTERFACE, ''),
            route.get(Route.DESTINATION, ''))


parametrize_ip_ver_routes = pytest.mark.parametrize(
    'get_routes_func',
    [(_get_ipv4_test_routes),
     (_get_ipv6_test_routes)],
    ids=['ipv4', 'ipv6'])


@parametrize_ip_ver_routes
def test_remove_specific_route(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        },
    })
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)

    absent_route = routes[0]
    absent_route[Route.STATE] = Route.STATE_ABSENT
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: [absent_route]
        },
    })

    expected_routes = routes[1:]

    cur_state = libnmstate.show()
    _assert_routes(expected_routes, cur_state)


@parametrize_ip_ver_routes
def test_remove_wildcast_route_with_iface(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        },
    })
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)

    absent_route = {
        Route.STATE: Route.STATE_ABSENT,
        Route.NEXT_HOP_INTERFACE: 'eth1'
    }
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: [absent_route]
        },
    })

    expected_routes = []

    cur_state = libnmstate.show()
    _assert_routes(expected_routes, cur_state)


@parametrize_ip_ver_routes
def test_remove_wildcast_route_without_iface(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: routes
        },
    })
    cur_state = libnmstate.show()
    _assert_routes(routes, cur_state)

    absent_routes = []
    for route in routes:
        absent_routes.append({
            Route.STATE: Route.STATE_ABSENT,
            Route.DESTINATION: route[Route.DESTINATION]
        })
    libnmstate.apply({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: absent_routes
        },
    })

    expected_routes = []

    cur_state = libnmstate.show()
    _assert_routes(expected_routes, cur_state)
