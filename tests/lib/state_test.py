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
from collections import defaultdict
import copy

import pytest

from libnmstate import state
from libnmstate.iplib import is_ipv6_address
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route


class TestAssertIfaceState(object):

    def test_desired_is_identical_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state

        desired_state.verify_interfaces(current_state)

    def test_desired_is_partial_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state
        extra_state = self._extra_state
        current_state.interfaces.update(extra_state.interfaces)

        desired_state.verify_interfaces(current_state)

    def test_current_is_partial_to_desired(self):
        desired_state = self._base_state
        current_state = self._base_state
        extra_state = self._extra_state
        desired_state.interfaces.update(extra_state.interfaces)

        with pytest.raises(NmstateVerificationError):
            desired_state.verify_interfaces(current_state)

    def test_desired_is_not_equal_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state
        current_state.interfaces['foo-name']['state'] = 'down'

        with pytest.raises(NmstateVerificationError):
            desired_state.verify_interfaces(current_state)

    def test_sort_multiple_ip(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state.interfaces['foo-name']['ipv4'] = {
            'address': [
                {
                    'ip': '192.168.122.10',
                    'prefix-length': 24
                },
                {
                    'ip': '192.168.121.10',
                    'prefix-length': 24
                },
            ],
            'enabled': True
        }
        current_state.interfaces['foo-name']['ipv4'] = {
            'address': [
                {
                    'ip': '192.168.121.10',
                    'prefix-length': 24
                },
                {
                    'ip': '192.168.122.10',
                    'prefix-length': 24
                },
            ],
            'enabled': True
        }
        desired_state.interfaces['foo-name']['ipv6'] = {
            'address': [
                {
                    'ip': '2001::2',
                    'prefix-length': 64
                },
                {
                    'ip': '2001::1',
                    'prefix-length': 64
                }
            ],
            'enabled': True
        }
        current_state.interfaces['foo-name']['ipv6'] = {
            'address': [
                {
                    'ip': '2001::1',
                    'prefix-length': 64
                },
                {
                    'ip': '2001::2',
                    'prefix-length': 64
                }
            ],
            'enabled': True
        }

        desired_state.verify_interfaces(current_state)

    @property
    def _base_state(self):
        return state.State({
            Interface.KEY: [
                {
                    'name': 'foo-name',
                    'type': 'foo-type',
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': 'system'}
                        ]
                    }
                }
            ]
        })

    @property
    def _extra_state(self):
        return state.State({
            Interface.KEY: [
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })


class TestAssertRouteState(object):
    def test_hash_unique(self):
        routes = _get_mixed_test_routes()
        assert (hash(state.RouteEntry(routes[0])) ==
                hash(state.RouteEntry(routes[0])))

    def test_obj_unique(self):
        routes = _get_mixed_test_routes()
        route = routes[0]
        new_route = copy.deepcopy(routes[0])
        assert state.RouteEntry(route) == state.RouteEntry(new_route)
        assert state.RouteEntry(route) != state.RouteEntry(routes[1])

    def test_obj_unique_without_table_id(self):
        routes = _get_mixed_test_routes()
        route_with_default_table_id = routes[0]
        route_without_table_id = copy.deepcopy(routes[0])
        route_with_default_table_id[Route.TABLE_ID] = \
            Route.USE_DEFAULT_ROUTE_TABLE
        del route_without_table_id[Route.TABLE_ID]
        assert (state.RouteEntry(route_without_table_id) ==
                state.RouteEntry(route_with_default_table_id))

    def test_obj_unique_without_metric(self):
        routes = _get_mixed_test_routes()
        route_with_default_metric = routes[0]
        route_without_metric = copy.deepcopy(routes[0])
        route_with_default_metric[Route.METRIC] = Route.USE_DEFAULT_METRIC
        del route_without_metric[Route.METRIC]
        assert (state.RouteEntry(route_without_metric) ==
                state.RouteEntry(route_with_default_metric))

    def test_obj_unique_without_next_hop(self):
        routes = _get_mixed_test_routes()
        route_with_default_next_hop = routes[0]
        route_without_next_hop = copy.deepcopy(routes[0])
        route_with_default_next_hop[Route.NEXT_HOP_ADDRESS] = ''
        del route_without_next_hop[Route.NEXT_HOP_ADDRESS]
        assert (state.RouteEntry(route_without_next_hop) ==
                state.RouteEntry(route_with_default_next_hop))

    def test_normal_route_object(self):
        routes = _get_mixed_test_routes()
        route = routes[0]
        route_obj = state.RouteEntry(route)
        assert route_obj.to_dict() == route

    def test_absent_route_object(self):
        routes = _get_mixed_test_routes()
        route = routes[0]
        route[Route.STATE] = Route.STATE_ABSENT
        route_obj = state.RouteEntry(route)
        assert route_obj.to_dict() == route

    def test_absent_wildcard(self):
        routes = _get_mixed_test_routes()
        original_route = routes[0]
        for prop_name in (Route.TABLE_ID, Route.DESTINATION,
                          Route.NEXT_HOP_INTERFACE, Route.NEXT_HOP_ADDRESS,
                          Route.METRIC):
            route = copy.deepcopy(original_route)
            route[Route.STATE] = Route.STATE_ABSENT
            del route[prop_name]
            route_obj = state.RouteEntry(route)
            assert route_obj.to_dict() == route

    def test_absent_exact_match(self):
        routes = _get_mixed_test_routes()
        routes[0][Route.STATE] = Route.STATE_ABSENT
        obj1 = state.RouteEntry(routes[0])
        del routes[0][Route.STATE]
        obj2 = state.RouteEntry(routes[0])
        obj3 = state.RouteEntry(routes[1])
        assert obj1.is_match(obj2)
        assert not obj1.is_match(obj3)

    def test_absent_wildcard_match(self):
        routes = _get_mixed_test_routes()
        original_route = routes[0]
        other_route_obj = state.RouteEntry(routes[1])
        original_route_obj = state.RouteEntry(original_route)
        for prop_name in (Route.TABLE_ID, Route.DESTINATION,
                          Route.NEXT_HOP_INTERFACE, Route.NEXT_HOP_ADDRESS,
                          Route.METRIC):
            route = copy.deepcopy(original_route)
            route[Route.STATE] = Route.STATE_ABSENT
            del route[prop_name]
            route_obj = state.RouteEntry(route)
            assert route_obj.is_match(original_route_obj)
            assert not route_obj.is_match(other_route_obj)

    def test_absent_cannot_remove_absent(self):
        routes = _get_mixed_test_routes()
        routes[0][Route.STATE] = Route.STATE_ABSENT
        obj1 = state.RouteEntry(routes[0])
        obj2 = state.RouteEntry(routes[0])
        assert not obj1.is_match(obj2)


def test_state_empty_routes():
    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: []
            }
        }
    )

    assert {} == route_state.config_iface_routes


def test_state_iface_routes_with_distinct_ifaces():
    routes = _get_mixed_test_routes()
    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: routes
            }
        }
    )
    expected_indexed_route_state = defaultdict(list)
    for route in routes:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        expected_indexed_route_state[iface_name].append(route)
        # No need to sort the routes as there is only 1 route per interface.

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_iface_routes_with_same_iface():
    routes = _get_mixed_test_routes()
    for route in routes:
        route[Route.NEXT_HOP_INTERFACE] = 'eth1'
    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: routes
            }
        }
    )
    expected_indexed_route_state = {
        'eth1': sorted(routes, key=_route_sort_key)
    }

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_iface_routes_order():
    # Changing all routes to eth1
    routes = _get_mixed_test_routes()
    for route in routes:
        route[Route.NEXT_HOP_INTERFACE] = 'eth1'

    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: [routes[0], routes[1]],
            }
        }
    )
    reverse_route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: [routes[1], routes[0]],
            }
        }
    )

    assert (route_state.config_iface_routes ==
            reverse_route_state.config_iface_routes)


def test_state_merge_config_add():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    other_state = state.State(
        {
            Interface.KEY: iface_states,
            Route.KEY: {
                Route.CONFIG: [routes[0]],
            }
        }
    )
    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: [routes[1]],
            }
        }
    )

    route_state.merge_route_config(other_state)

    expected_indexed_route_state = defaultdict(list)
    for route in routes[:2]:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        expected_indexed_route_state[iface_name].append(route)
        # No need to sort the routes as there is only 1 route per interface.

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_merge_config_add_duplicate():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    other_state = state.State(
        {
            Interface.KEY: iface_states,
            Route.KEY: {
                Route.CONFIG: routes,
            }
        }
    )
    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: [routes[0]],
            }
        }
    )

    route_state.merge_route_config(other_state)

    expected_indexed_route_state = defaultdict(list)
    for route in routes:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        expected_indexed_route_state[iface_name].append(route)
        # No need to sort the routes as there is only 1 route per interface.

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_merge_config_add_empty():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    other_state = state.State(
        {
            Interface.KEY: iface_states,
            Route.KEY: {
                Route.CONFIG: routes,
            }
        }
    )
    route_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: []
            }
        }
    )
    route_state.merge_route_config(other_state)

    expected_indexed_route_state = defaultdict(list)
    for route in routes:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        expected_indexed_route_state[iface_name].append(route)
        # No need to sort the routes as there is only 1 route per interface.

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_merge_config_discard_absent():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    for route in routes:
        route[Route.STATE] = Route.STATE_ABSENT
    other_state = state.State(
        {
            Route.KEY: {
                Route.CONFIG: [],
            }
        }
    )
    route_state = state.State(
        {
            Interface.KEY: iface_states,
            Route.KEY: {
                Route.CONFIG: routes
            }
        }
    )
    route_state.merge_route_config(other_state)

    expected_indexed_route_state = {}
    assert expected_indexed_route_state == route_state.config_iface_routes


def test_merge_desired_route_iface_down():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    iface_states[0][Interface.STATE] = InterfaceState.DOWN
    desired_state = state.State(
        {
            Interface.KEY: iface_states,
            Route.KEY: {
                Route.CONFIG: routes,
            }
        }
    )
    with pytest.raises(NmstateValueError):
        desired_state.merge_route_config(state.State({}))


def test_merge_desired_route_iface_missing():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    routes[0][Route.NEXT_HOP_INTERFACE] = 'not_exists'
    desired_state = state.State(
        {
            Interface.KEY: iface_states,
            Route.KEY: {
                Route.CONFIG: routes,
            }
        }
    )
    with pytest.raises(NmstateValueError):
        desired_state.merge_route_config(state.State({}))


def test_merge_desired_route_ip_disabled():
    routes = _get_mixed_test_routes()
    ipv4_routes = []
    ipv6_routes = []

    for route in routes:
        if is_ipv6_address(route[Route.DESTINATION]):
            ipv6_routes.append(route)
        else:
            ipv4_routes.append(route)
    for routes in (ipv4_routes, ipv6_routes):
        iface_states = _gen_iface_states_for_routes(routes)
        iface_states[0][Interface.IPV4]['enabled'] = False
        iface_states[0][Interface.IPV6]['enabled'] = False
        desired_state = state.State(
            {
                Interface.KEY: iface_states,
                Route.KEY: {
                    Route.CONFIG: routes,
                }
            }
        )
        with pytest.raises(NmstateValueError):
            desired_state.merge_route_config(state.State({}))


def test_state_verify_route_same():
    routes = _get_mixed_test_routes()
    route_state = state.State({
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    route_state_2 = state.State({
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    route_state.verify_routes(route_state_2)


def test_state_verify_route_diff_route_count():
    routes = _get_mixed_test_routes()
    route_state = state.State({
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    route_state_2 = state.State({
        Route.KEY: {
            Route.CONFIG: routes[:1]
        }
    })

    with pytest.raises(NmstateVerificationError):
        route_state.verify_routes(route_state_2)


def test_state_verify_route_diff_route_prop():
    routes = _get_mixed_test_routes()
    route_state = state.State({
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    routes[0][Route.NEXT_HOP_INTERFACE] = 'another_nic'
    route_state_2 = state.State({
        Route.KEY: {
            Route.CONFIG: routes
        }
    })

    with pytest.raises(NmstateVerificationError):
        route_state.verify_routes(route_state_2)


def test_state_verify_route_empty():
    route_state = state.State({})
    route_state_2 = state.State({})
    route_state.verify_routes(route_state_2)


def test_state_merge_config_specific_remove():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    current_state = state.State({
        Interface.KEY: iface_states,
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    absent_route = routes[0]
    absent_route[Route.STATE] = Route.STATE_ABSENT
    desired_state = state.State({
        Interface.KEY: iface_states,
        Route.KEY: {
            Route.CONFIG: [absent_route]
        }
    })

    desired_state.merge_route_config(current_state)

    expected_indexed_route_state = defaultdict(list)
    for route in routes[1:]:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        expected_indexed_route_state[iface_name].append(route)
        # No need to sort the routes as there is only 1 route per interface.

    assert expected_indexed_route_state == desired_state.config_iface_routes


def test_state_remote_route_wildcard_with_iface():
    routes = _get_mixed_test_routes()
    iface_states = _gen_iface_states_for_routes(routes)
    current_state = state.State({
        Interface.KEY: iface_states,
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    absent_route_iface_name = routes[0][Route.NEXT_HOP_INTERFACE]
    absent_route = {
        Route.STATE: Route.STATE_ABSENT,
        Route.NEXT_HOP_INTERFACE: absent_route_iface_name
    }
    desired_state = state.State({
        Interface.KEY: iface_states,
        Route.KEY: {
            Route.CONFIG: [absent_route]
        }
    })

    desired_state.merge_route_config(current_state)

    expected_indexed_route_state = defaultdict(list)
    for route in routes:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        if iface_name != absent_route_iface_name:
            expected_indexed_route_state[iface_name].append(route)
            # No need to sort the routes as there is only 1 route per
            # interface.

    assert expected_indexed_route_state == desired_state.config_iface_routes


def test_state_remote_route_wildcard_destination_without_iface():
    routes = _get_mixed_test_routes()
    current_state = state.State({
        Route.KEY: {
            Route.CONFIG: routes
        }
    })
    absent_routes = []
    for route in routes:
        absent_routes.append({
            Route.STATE: Route.STATE_ABSENT,
            Route.DESTINATION: route[Route.DESTINATION]
        })
    desired_state = state.State({
        Route.KEY: {
            Route.CONFIG: absent_routes
        }
    })

    desired_state.merge_route_config(current_state)

    expected_indexed_route_state = {}
    assert expected_indexed_route_state == desired_state.config_iface_routes


def _get_mixed_test_routes():
    return [
        {
            Route.DESTINATION: '198.51.100.0/24',
            Route.METRIC: 103,
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.TABLE_ID: 50
        },
        {
            Route.DESTINATION: '2001:db8:a::/64',
            Route.METRIC: 104,
            Route.NEXT_HOP_INTERFACE: 'eth2',
            Route.NEXT_HOP_ADDRESS: '2001:db8:1::a',
            Route.TABLE_ID: 51
        }
    ]


def _gen_iface_states_for_routes(routes):
    ifaces = set([route[Route.NEXT_HOP_INTERFACE] for route in routes])
    return [
        {
            Interface.NAME: iface,
            Interface.STATE: InterfaceState.UP,
            Interface.IPV4: {
                'enabled': True
            },
            Interface.IPV6: {
                'enabled': True
            }
        }
        for iface in ifaces
    ]


def _route_sort_key(route):
    return (route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
            route.get(Route.NEXT_HOP_INTERFACE, ''),
            route.get(Route.DESTINATION, ''))
