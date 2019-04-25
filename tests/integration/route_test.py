#
# Copyright 2018 Red Hat, Inc.
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

from .testlib import statelib

IPV4_ADDRESS1 = '192.0.2.251'
IPV4_ROUTE1 = {
    'destination': '198.51.100.0/24',
    'metric': 103,
    'next-hop-address': '192.0.2.1',
    'next-hop-interface': 'eth1',
    'table-id': 50
}
IPV4_ROUTE2 = {
    'destination': '203.0.113.0/24',
    'metric': 103,
    'next-hop-address': '192.0.2.1',
    'next-hop-interface': 'eth1',
    'table-id': 51
}
IPV4_GATEWAY1 = {
    'destination': '0.0.0.0/0',
    'metric': 103,
    'next-hop-address': '192.0.2.1',
    'next-hop-interface': 'eth1',
    'table-id': 254
}
IPV4_GATEWAY2 = {
    'destination': '0.0.0.0/0',
    'metric': 101,
    'next-hop-address': '192.0.2.2',
    'next-hop-interface': 'eth1',
    'table-id': 254
}
IPV6_ADDRESS1 = '2001:db8:1::1'
IPV6_ROUTE1 = {
    'destination': '2001:db8:a::/64',
    'metric': 103,
    'next-hop-address': '2001:db8:1::a',
    'next-hop-interface': 'eth1',
    'table-id': 50
}
IPV6_ROUTE2 = {
    'destination': '2001:db8:b::/64',
    'metric': 103,
    'next-hop-address': '2001:db8:1::b',
    'next-hop-interface': 'eth1',
    'table-id': 50
}
IPV6_GATEWAY1 = {
    'destination': '::/0',
    'metric': 103,
    'next-hop-address': '2001:db8:1::f',
    'next-hop-interface': 'eth1',
    'table-id': 254
}
IPV6_GATEWAY2 = {
    'destination': '::/0',
    'metric': 101,
    'next-hop-address': '2001:db8:1::e',
    'next-hop-interface': 'eth1',
    'table-id': 254
}


@pytest.fixture(scope='function', autouse=True)
def eth1_set_static_ip_no_route(eth1_up):
    clean_config = {
        'routes': {
            'config': [
                {
                    # Below lines will remove all static routes on eth1
                    'state': 'absent',
                    'next-hop-interface': 'eth1'
                },
            ]
        },
        'interfaces': [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'address': [
                        {
                            'ip': IPV4_ADDRESS1,
                            'prefix-length': 24
                        }
                    ],
                    'enabled': True
                },
                'ipv6': {
                    'address': [
                        {
                            'ip': IPV6_ADDRESS1,
                            'prefix-length': 64
                        }
                    ],
                    'enabled': True
                },
                'mtu': 1500
            },
        ]
    }
    netapplier.apply(clean_config)


def test_add_static_routes():
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV4_ROUTE2,
                    IPV6_ROUTE1,
                    IPV6_ROUTE2,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_has_route(IPV4_ROUTE1, cur_state)
    _assert_has_route(IPV4_ROUTE2, cur_state)
    _assert_has_route(IPV6_ROUTE1, cur_state)
    _assert_has_route(IPV6_ROUTE2, cur_state)


def test_change_gateway():
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_GATEWAY1,
                    IPV6_GATEWAY1,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_has_route(IPV4_GATEWAY1, cur_state)
    _assert_has_route(IPV6_GATEWAY1, cur_state)

    netapplier.apply(
        {
            'routes': {
                'config': [
                    {
                        'state': 'absent',
                        'destination': '0.0.0.0/0',
                        'next-hop-interface': 'eth1'
                    },
                    IPV4_GATEWAY2,
                    {
                        'state': 'absent',
                        'destination': '::/0',
                        'next-hop-interface': 'eth1'
                    },
                    IPV6_GATEWAY2,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_not_has_route(IPV4_GATEWAY1, cur_state)
    _assert_not_has_route(IPV6_GATEWAY1, cur_state)
    _assert_has_route(IPV4_GATEWAY2, cur_state)
    _assert_has_route(IPV6_GATEWAY2, cur_state)


def test_add_route_no_metric():
    del IPV4_ROUTE1['metric']
    del IPV6_ROUTE1['metric']
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV6_ROUTE1,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    IPV4_ROUTE1['metric'] = -1
    IPV6_ROUTE1['metric'] = -1
    _assert_has_route(IPV4_ROUTE1, cur_state)
    _assert_has_route(IPV6_ROUTE1, cur_state)


def test_add_route_no_table_id():
    del IPV4_ROUTE1['table-id']
    del IPV6_ROUTE1['table-id']
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV6_ROUTE1,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    IPV4_ROUTE1['table-id'] = 0
    IPV6_ROUTE1['table-id'] = 0
    _assert_has_route(IPV4_ROUTE1, cur_state)
    _assert_has_route(IPV6_ROUTE1, cur_state)


def test_two_ipv4_gateways():
    with pytest.raises(NmstateNotImplementedError):
        netapplier.apply(
            {
                'routes': {
                    'config': [
                        IPV4_GATEWAY1,
                        IPV4_GATEWAY2
                    ]
                },
            })


def test_two_ipv6_gateways():
    with pytest.raises(NmstateNotImplementedError):
        netapplier.apply(
            {
                'routes': {
                    'config': [
                        IPV6_GATEWAY1,
                        IPV6_GATEWAY2
                    ]
                },
            })


def test_remove_routes_without_iface_defined():
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV4_ROUTE2,
                    IPV6_ROUTE1,
                    IPV6_ROUTE2,
                ]
            },
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_has_route(IPV4_ROUTE1, cur_state)
    _assert_has_route(IPV6_ROUTE1, cur_state)
    _assert_has_route(IPV4_ROUTE2, cur_state)
    _assert_has_route(IPV6_ROUTE2, cur_state)
    netapplier.apply(
        {
            'routes': {
                'config': [
                    {
                        'state': 'absent',
                        'destination': IPV4_ROUTE1['destination'],
                    },
                    {
                        'state': 'absent',
                        'destination': IPV6_ROUTE1['destination'],
                    },
                ]
            },
        })

    cur_state = statelib.show_only(('eth1',))
    _assert_has_route(IPV4_ROUTE2, cur_state)
    _assert_has_route(IPV6_ROUTE2, cur_state)
    _assert_not_has_route(IPV4_ROUTE1, cur_state)
    _assert_not_has_route(IPV6_ROUTE1, cur_state)


def test_remove_routes_with_iface_defined():
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV4_ROUTE2,
                    IPV6_ROUTE1,
                    IPV6_ROUTE2,
                ]
            },
        })
    netapplier.apply(
        {
            'routes': {
                'config': [
                    {
                        'state': 'absent',
                        'destination': IPV4_ROUTE1['destination'],
                    },
                    {
                        'state': 'absent',
                        'destination': IPV6_ROUTE1['destination'],
                    },
                ]
            },
        })

    cur_state = statelib.show_only(('eth1',))
    _assert_has_route(IPV4_ROUTE2, cur_state)
    _assert_has_route(IPV6_ROUTE2, cur_state)
    _assert_not_has_route(IPV4_ROUTE1, cur_state)
    _assert_not_has_route(IPV6_ROUTE1, cur_state)


def test_add_route_on_down_iface():
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV6_ROUTE1,
                ]
            },
            'interfaces': [
                {
                    'name': 'eth1',
                    'type': 'ethernet',
                    'state': 'down',
                }
            ]
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_not_has_route(IPV4_ROUTE1, cur_state)
    _assert_not_has_route(IPV6_ROUTE1, cur_state)


def test_add_route_on_down_ipv4():
    netapplier.apply(
        {
            'routes': {
                'config': [
                    IPV4_ROUTE1,
                    IPV6_ROUTE1,
                ]
            },
            'interfaces': [
                {
                    'name': 'eth1',
                    'type': 'ethernet',
                    'state': 'up',
                    'ipv4': {
                        'enabled': False
                    }
                }
            ]
        })
    cur_state = statelib.show_only(('eth1',))
    _assert_not_has_route(IPV4_ROUTE1, cur_state)
    _assert_has_route(IPV6_ROUTE1, cur_state)


# We cannot disable IPv6, once we do, add test 'test_add_route_on_down_ipv6'


def _assert_has_route(route, state):
    assert route in state['routes']['config']

    # For running route, the default(-1) metric and route-table will be
    # changed. Hence should be ignored.
    tmp_route = copy.deepcopy(route)
    run_routes = copy.deepcopy(state['routes']['running'])
    for prop_name, default_value in (('metric', -1), ('table-id', 0)):
        if tmp_route[prop_name] == default_value:
            del tmp_route[prop_name]
            for run_route in run_routes:
                del run_route[prop_name]
    assert tmp_route in run_routes


def _assert_not_has_route(route, state):
    for routes in (state['routes']['running'], state['routes']['config']):
        assert route not in routes
