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

from libnmstate import netapplier
from libnmstate.error import NmstateNotImplementedError
from libnmstate.schema import Interface
from libnmstate.schema import Route

from .testlib import statelib

IPV4_ADDRESS1 = '192.0.2.251'

IPV4_ROUTE1 = {
    Route.DESTINATION: '198.51.100.0/24',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '192.0.2.1',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 50
}

IPV4_ROUTE2 = {
    Route.DESTINATION: '203.0.113.0/24',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '192.0.2.1',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 51
}

IPV4_GATEWAY1 = {
    Route.DESTINATION: '0.0.0.0/0',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '192.0.2.1',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 254
}

IPV4_GATEWAY2 = {
    Route.DESTINATION: '0.0.0.0/0',
    Route.METRIC: 101,
    Route.NEXT_HOP_ADDRESS: '192.0.2.2',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 254
}

IPV6_ADDRESS1 = '2001:db8:1::1'

IPV6_ROUTE1 = {
    Route.DESTINATION: '2001:db8:a::/64',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '2001:db8:1::a',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 50
}

IPV6_ROUTE2 = {
    Route.DESTINATION: '2001:db8:b::/64',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '2001:db8:1::b',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 50
}

IPV6_GATEWAY1 = {
    Route.DESTINATION: '::/0',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '2001:db8:1::f',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 254
}

IPV6_GATEWAY2 = {
    Route.DESTINATION: '::/0',
    Route.METRIC: 101,
    Route.NEXT_HOP_ADDRESS: '2001:db8:1::e',
    Route.NEXT_HOP_INTERFACE: 'eth1',
    Route.TABLE_ID: 254
}

ETH1_INTERFACE_STATE = {
    'name': 'eth1',
    'state': 'up',
    'type': 'ethernet',
    'ipv4': {
        'address': [
            {
                'ip': IPV4_ADDRESS1,
                'prefix-length': 24
            }
        ],
        'dhcp': False,
        'enabled': True
    },
    'ipv6': {
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
    netapplier.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    IPV4_ROUTE1,
                    IPV4_ROUTE2,
                    IPV6_ROUTE1,
                    IPV6_ROUTE2,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_route(IPV4_ROUTE1, cur_state)
    _assert_route(IPV4_ROUTE2, cur_state)
    _assert_route(IPV6_ROUTE1, cur_state)
    _assert_route(IPV6_ROUTE2, cur_state)


def test_add_route_without_metric(eth1_up):
    desired_state = copy.deepcopy({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: [
                IPV4_ROUTE1,
                IPV4_ROUTE2,
                IPV6_ROUTE1,
                IPV6_ROUTE2,
            ]
        },
    })
    for route in desired_state[Route.KEY][Route.CONFIG]:
        del route[Route.METRIC]
    netapplier.apply(desired_state)
    cur_state = statelib.show_only(('eth1',))
    for route in desired_state[Route.KEY][Route.CONFIG]:
        _assert_route(route, cur_state)


def test_add_route_without_table_id(eth1_up):
    desired_state = copy.deepcopy({
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {
            Route.CONFIG: [
                IPV4_ROUTE1,
                IPV4_ROUTE2,
                IPV6_ROUTE1,
                IPV6_ROUTE2,
            ]
        },
    })
    for route in desired_state[Route.KEY][Route.CONFIG]:
        del route[Route.TABLE_ID]
    netapplier.apply(desired_state)
    cur_state = statelib.show_only(('eth1',))
    for route in desired_state[Route.KEY][Route.CONFIG]:
        _assert_route(route, cur_state)


def test_add_route_without_iface_state(eth1_up):
    netapplier.apply({Interface.KEY: [ETH1_INTERFACE_STATE]})

    netapplier.apply({
        Interface.KEY: [],
        Route.KEY: {
            Route.CONFIG: [
                IPV4_ROUTE1,
                IPV4_ROUTE2,
                IPV6_ROUTE1,
                IPV6_ROUTE2,
            ]
        },
    })
    cur_state = statelib.show_only(('eth1',))
    _assert_route(IPV4_ROUTE1, cur_state)
    _assert_route(IPV4_ROUTE2, cur_state)
    _assert_route(IPV6_ROUTE1, cur_state)
    _assert_route(IPV6_ROUTE2, cur_state)


@pytest.mark.xfail(raises=NmstateNotImplementedError,
                   reason="Red Hat Bug 1707396")
def test_multiple_gateway(eth1_up):
    netapplier.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    IPV4_GATEWAY1,
                    IPV4_GATEWAY2,
                    IPV6_GATEWAY1,
                    IPV6_GATEWAY2,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_route(IPV4_GATEWAY1, cur_state)
    _assert_route(IPV4_GATEWAY2, cur_state)
    _assert_route(IPV6_GATEWAY1, cur_state)
    _assert_route(IPV6_GATEWAY2, cur_state)


def _assert_route(route, state):
    if Route.METRIC not in route:
        route[Route.METRIC] = -1
    if Route.TABLE_ID not in route:
        route[Route.TABLE_ID] = 0
    assert route in state[Route.KEY][Route.CONFIG]

    # For running route, the default (-1) metric and route-table will be
    # changed. Hence should be ignored.
    tmp_route = copy.deepcopy(route)
    run_routes = copy.deepcopy(state[Route.KEY][Route.RUNNING])
    for prop_name, default_value in ((Route.METRIC, -1), (Route.TABLE_ID, 0)):
        if tmp_route[prop_name] == default_value:
            del tmp_route[prop_name]
            for run_route in run_routes:
                del run_route[prop_name]
    assert tmp_route in run_routes
