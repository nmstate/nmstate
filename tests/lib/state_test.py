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
    IPV4_ROUTE1_IFACE_NAME = 'eth1'

    IPV4_ROUTE1 = {
        Route.DESTINATION: '198.51.100.0/24',
        Route.METRIC: 102,
        Route.NEXT_HOP_ADDRESS: '192.0.2.2',
        Route.NEXT_HOP_INTERFACE: IPV4_ROUTE1_IFACE_NAME,
        Route.TABLE_ID: 254
    }

    IPV4_ROUTE2_IFACE_NAME = 'eth2'

    IPV4_ROUTE2 = {
        Route.DESTINATION: '203.0.113.0/24',
        Route.METRIC: 102,
        Route.NEXT_HOP_ADDRESS: '192.0.2.2',
        Route.NEXT_HOP_INTERFACE: IPV4_ROUTE2_IFACE_NAME,
        Route.TABLE_ID: 254
    }

    def test_merge_route_add(self):
        """
        Test adding routes with old routes preserved.
        """
        current_state = state.State(self._base_state_dict)
        desired_state_dict = copy.deepcopy(self._base_state_dict)
        new_route = copy.deepcopy(TestAssertRouteState.IPV4_ROUTE1)
        new_route[Route.NEXT_HOP_ADDRESS] = '192.0.2.3'
        desired_state_dict[Route.KEY][Route.CONFIG] = [new_route]
        desired_state = state.State(desired_state_dict)
        desired_state.merge_route_config(current_state)

        assert new_route in desired_state.iface_routes['eth1']
        iface_routes = desired_state.iface_routes
        # Old routes should be no touched
        assert (TestAssertRouteState.IPV4_ROUTE1 in
                iface_routes[TestAssertRouteState.IPV4_ROUTE1_IFACE_NAME])
        # Interface without changes should not be included
        assert (TestAssertRouteState.IPV4_ROUTE2 not in
                iface_routes[TestAssertRouteState.IPV4_ROUTE2_IFACE_NAME])

    def test_merge_route_add_without_iface(self):
        """
        Test desired_state only contains routes without any interface defined.
        """
        current_state = state.State(self._base_state_dict)
        desired_state_dict = copy.deepcopy(self._base_state_dict)
        new_route = copy.deepcopy(TestAssertRouteState.IPV4_ROUTE1)
        new_route[Route.NEXT_HOP_ADDRESS] = '192.0.2.3'
        desired_state_dict[Route.KEY][Route.CONFIG] = [new_route]
        desired_state_dict[Interface.KEY] = {}
        desired_state = state.State(desired_state_dict)
        changed_iface_names = desired_state.merge_route_config(current_state)
        desired_state.include_changed_interfaces(current_state,
                                                 changed_iface_names)

        assert (new_route[Route.NEXT_HOP_INTERFACE] in
                desired_state.interfaces)

    def test_verify_routes_add_route(self):
        """
        Test route verification with the ordering of routes
        """
        current_state = state.State(self._base_state_dict)
        desired_state_dict = copy.deepcopy(self._base_state_dict)
        tmp_route = desired_state_dict[Route.KEY][Route.CONFIG][0]
        desired_state_dict[Route.KEY][Route.CONFIG][0] = \
            desired_state_dict[Route.KEY][Route.CONFIG][1]
        desired_state_dict[Route.KEY][Route.CONFIG][1] = tmp_route
        desired_state = state.State(desired_state_dict)
        desired_state.verify_routes(current_state)

    def test_add_route_without_metric(self):
        current_state = state.State(self._base_state_dict)
        desired_state_dict = copy.deepcopy(self._base_state_dict)
        new_route = copy.deepcopy(TestAssertRouteState.IPV4_ROUTE1)
        del new_route[Route.METRIC]
        desired_state_dict[Route.KEY][Route.CONFIG] = [new_route]
        desired_state_dict[Interface.KEY] = {}
        desired_state = state.State(desired_state_dict)
        desired_state.merge_route_config(current_state)
        new_route[Route.METRIC] = Route.USE_DEFAULT_METRIC

        assert (new_route in
                desired_state.iface_routes[
                    new_route[Route.NEXT_HOP_INTERFACE]])

    def test_add_route_without_route_table_id(self):
        current_state = state.State(self._base_state_dict)
        desired_state_dict = copy.deepcopy(self._base_state_dict)
        new_route = copy.deepcopy(TestAssertRouteState.IPV4_ROUTE1)
        del new_route[Route.TABLE_ID]
        desired_state_dict[Route.KEY][Route.CONFIG] = [new_route]
        desired_state_dict[Interface.KEY] = {}
        desired_state = state.State(desired_state_dict)
        desired_state.merge_route_config(current_state)
        new_route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE

        assert (new_route in
                desired_state.iface_routes[
                    new_route[Route.NEXT_HOP_INTERFACE]])

    @property
    def _base_state_dict(self):
        return {
            Route.KEY: {
                Route.CONFIG: [
                    TestAssertRouteState.IPV4_ROUTE1,
                    TestAssertRouteState.IPV4_ROUTE2
                ]
            },
            Interface.KEY: [
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        }
