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

from libnmstate import state
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface
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
