#
# Copyright (c) 2019-2020 Red Hat, Inc.
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
from collections import defaultdict
import copy

import pytest

from libnmstate import state
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge
from libnmstate.schema import OVSBridge
from libnmstate.schema import Route
from libnmstate.schema import RouteRule


parametrize_route_property = pytest.mark.parametrize(
    "route_property",
    [
        Route.TABLE_ID,
        Route.DESTINATION,
        Route.NEXT_HOP_INTERFACE,
        Route.NEXT_HOP_ADDRESS,
        Route.METRIC,
    ],
)


class TestAssertIfaceState:
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
        current_state.interfaces["foo-name"][
            Interface.STATE
        ] = InterfaceState.DOWN

        with pytest.raises(NmstateVerificationError):
            desired_state.verify_interfaces(current_state)

    def test_desired_has_extra_info_when_ip_disabled(self):
        desired_state = self._base_state
        desired_state.interfaces["foo-name"][Interface.IPV4] = {
            InterfaceIPv4.ENABLED: False,
            InterfaceIPv4.DHCP: False,
        }
        desired_state.interfaces["foo-name"][Interface.IPV6] = {
            InterfaceIPv6.ENABLED: False,
            InterfaceIPv6.DHCP: False,
            InterfaceIPv6.AUTOCONF: False,
        }
        current_state = self._base_state
        current_state.interfaces["foo-name"][Interface.IPV4] = {
            InterfaceIPv4.ENABLED: False
        }
        current_state.interfaces["foo-name"][Interface.IPV6] = {
            InterfaceIPv6.ENABLED: False
        }

        desired_state.verify_interfaces(current_state)

    def test_sort_multiple_ip(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state.interfaces["foo-name"][Interface.IPV4] = {
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.168.122.10",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                },
                {
                    InterfaceIPv4.ADDRESS_IP: "192.168.121.10",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                },
            ],
            InterfaceIPv4.ENABLED: True,
        }
        current_state.interfaces["foo-name"][Interface.IPV4] = {
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.168.121.10",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                },
                {
                    InterfaceIPv4.ADDRESS_IP: "192.168.122.10",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                },
            ],
            InterfaceIPv4.ENABLED: True,
        }
        desired_state.interfaces["foo-name"][Interface.IPV6] = {
            InterfaceIPv6.ADDRESS: [
                {
                    InterfaceIPv6.ADDRESS_IP: "2001::2",
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                },
                {
                    InterfaceIPv6.ADDRESS_IP: "2001::1",
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                },
            ],
            InterfaceIPv6.ENABLED: True,
        }
        current_state.interfaces["foo-name"][Interface.IPV6] = {
            InterfaceIPv6.ADDRESS: [
                {
                    InterfaceIPv6.ADDRESS_IP: "2001::1",
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                },
                {
                    InterfaceIPv6.ADDRESS_IP: "2001::2",
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                },
            ],
            InterfaceIPv6.ENABLED: True,
        }

        desired_state.verify_interfaces(current_state)

    def test_description_is_empty(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state.interfaces["foo-name"][Interface.DESCRIPTION] = ""

        desired_state.verify_interfaces(current_state)

    def test_description_is_not_empty(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state.interfaces["foo-name"][Interface.DESCRIPTION] = "bar"
        current_state.interfaces["foo-name"][Interface.DESCRIPTION] = "bar"

        desired_state.verify_interfaces(current_state)

    def test_accept_expanded_ipv6_notation(self):
        desired_state = self._base_state
        current_state = self._base_state
        expanded_ipv6_addr = "2001:0db8:85a3:0000:0000:8a2e:0370:7331"

        desired_state.interfaces["foo-name"][Interface.IPV6] = {
            InterfaceIPv6.ADDRESS: [
                {
                    InterfaceIPv6.ADDRESS_IP: expanded_ipv6_addr,
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            ],
            InterfaceIPv6.ENABLED: True,
        }
        current_state.interfaces["foo-name"][Interface.IPV6] = {
            InterfaceIPv6.ADDRESS: [
                {
                    InterfaceIPv6.ADDRESS_IP: "2001:db8:85a3::8a2e:370:7331",
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            ],
            InterfaceIPv6.ENABLED: True,
        }
        desired_state.verify_interfaces(current_state)

    def test_unmanaged_bridge_port_known_type(self):
        desired_state_raw = {
            Interface.KEY: [
                {
                    Interface.NAME: "bridge00",
                    Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                    Interface.STATE: InterfaceState.UP,
                    LinuxBridge.CONFIG_SUBTREE: {LinuxBridge.PORT_SUBTREE: []},
                }
            ]
        }
        desired_state = state.State(desired_state_raw)

        current_state_raw = copy.deepcopy(desired_state_raw)
        brstate = current_state_raw[Interface.KEY][0]
        brstate[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE].append(
            {LinuxBridge.Port.NAME: "eth0"}
        )
        current_state_raw[Interface.KEY].append(
            {
                Interface.NAME: "eth0",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.DOWN,
            }
        )
        current_state = state.State(current_state_raw)

        desired_state.verify_interfaces(current_state)

    def test_unmanaged_bridge_port_unknown_type(self):
        desired_state_raw = {
            Interface.KEY: [
                {
                    Interface.NAME: "bridge00",
                    Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                    Interface.STATE: InterfaceState.UP,
                    LinuxBridge.CONFIG_SUBTREE: {LinuxBridge.PORT_SUBTREE: []},
                }
            ]
        }
        desired_state = state.State(desired_state_raw)

        current_state_raw = copy.deepcopy(desired_state_raw)
        brstate = current_state_raw[Interface.KEY][0]
        brstate[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE].append(
            {LinuxBridge.Port.NAME: "eth0"}
        )
        current_state_raw[Interface.KEY].append(
            {
                Interface.NAME: "eth0",
                Interface.TYPE: InterfaceType.UNKNOWN,
                Interface.STATE: InterfaceState.UP,
            }
        )
        current_state = state.State(current_state_raw)

        desired_state.verify_interfaces(current_state)

    def test_ignore_current_unmanaged_bridge(self):
        desired_state = state.State({Interface.KEY: []})
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "bridge00",
                        Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )

        desired_state.verify_interfaces(current_state)

    @property
    def _base_state(self):
        return state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "foo-name",
                        Interface.TYPE: "foo-type",
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: {
                            OVSBridge.PORT_SUBTREE: [
                                {OVSBridge.Port.NAME: "eth0"}
                            ]
                        },
                    }
                ]
            }
        )

    @property
    def _extra_state(self):
        return state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "eth0",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )


class TestRouteEntry:
    def test_hash_unique(self):
        route = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)
        assert hash(route) == hash(route)

    def test_obj_unique(self):
        route0 = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)
        route1 = _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )
        route0_clone = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        assert route0 == route0_clone
        assert route0 != route1

    def test_obj_unique_without_table_id(self):
        route_with_default_table_id = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            Route.USE_DEFAULT_ROUTE_TABLE,
            103,
        )

        route_without_table_id = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", None, 103
        )

        assert route_without_table_id == route_with_default_table_id

    def test_obj_unique_without_metric(self):
        route_with_default_metric = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            50,
            Route.USE_DEFAULT_METRIC,
        )

        route_without_metric = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, None
        )

        assert route_without_metric == route_with_default_metric

    def test_obj_unique_without_next_hop(self):
        route_with_default_next_hop = _create_route(
            "198.51.100.0/24", "", "eth1", 50, 103
        )

        route_without_next_hop = _create_route(
            "198.51.100.0/24", None, "eth1", 50, 103
        )

        assert route_without_next_hop == route_with_default_next_hop

    def test_normal_route_object_as_dict(self):
        route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        route_obj = state.RouteEntry(route)
        assert route_obj.to_dict() == route

    def test_absent_route_object_as_dict(self):
        route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        route[Route.STATE] = Route.STATE_ABSENT
        route_obj = state.RouteEntry(route)
        assert route_obj.absent
        assert route_obj.to_dict() == route

    @parametrize_route_property
    def test_absent_route_with_missing_props_as_dict(self, route_property):
        absent_route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        absent_route[Route.STATE] = Route.STATE_ABSENT
        del absent_route[route_property]
        route_obj = state.RouteEntry(absent_route)
        assert route_obj.to_dict() == absent_route

    def test_absent_route_with_exact_match(self):
        route0 = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)

        absent_r0 = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        absent_r0[Route.STATE] = Route.STATE_ABSENT
        absent_route0 = state.RouteEntry(absent_r0)

        route1 = _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )

        assert absent_route0.match(route0)
        assert absent_route0 == route0
        assert not absent_route0.match(route1)
        assert absent_route0 != route1

    @parametrize_route_property
    def test_absent_route_wildcard_match(self, route_property):
        original_route0 = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        original_route1 = _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )

        absent_route0_state = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        absent_route0_state[Route.STATE] = Route.STATE_ABSENT
        del absent_route0_state[route_property]
        new_route0 = state.RouteEntry(absent_route0_state)

        assert new_route0.match(original_route0)
        assert not new_route0.match(original_route1)

    def test_absent_route_is_ignored_for_matching_and_equality(self):
        route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        route[Route.STATE] = Route.STATE_ABSENT
        obj1 = state.RouteEntry(route)
        obj2 = state.RouteEntry(route)
        assert obj1.match(obj2)
        assert obj1 == obj2

    def test_sort_routes(self):
        routes = [
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 103),
        ]
        expected_routes = [
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
        ]
        assert expected_routes == sorted(routes)

    @parametrize_route_property
    def test_sort_routes_with_absent_route(self, route_property):
        absent_route = _create_route(
            "198.51.100.0/24", "192.0.1.1", "eth0", 9, 103
        ).to_dict()
        absent_route[Route.STATE] = Route.STATE_ABSENT
        del absent_route[route_property]
        absent_route = state.RouteEntry(absent_route)
        routes = [
            absent_route,
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 103),
        ]
        expected_routes = [
            absent_route,
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
        ]
        assert expected_routes == sorted(routes)


class TestRouteStateMerge:
    def test_merge_empty_states(self):
        s0 = state.State({})
        s1 = state.State({})

        s0.merge_routes(s1)

        assert {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}} == s0.state
        assert {} == s0.config_iface_routes

    def test_merge_identical_states(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        s0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})
        s1 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        s0.merge_routes(s1)

        assert {
            Interface.KEY: [],
            Route.KEY: {Route.CONFIG: [route0]},
        } == s0.state
        assert {"eth1": [route0_obj]} == s0.config_iface_routes

    def test_merge_unique_states(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        route1_obj = self._create_route1()
        route1 = route1_obj.to_dict()
        s0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})
        s1 = state.State({Route.KEY: {Route.CONFIG: [route1]}})

        s0.merge_routes(s1)

        expected_state = {
            Interface.KEY: [],
            Route.KEY: {Route.CONFIG: [route0]},
        }
        assert expected_state == s0.state
        expected_indexed_routes = {"eth1": [route0_obj]}
        assert expected_indexed_routes == s0.config_iface_routes

    def test_merge_empty_with_non_empty_state(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        empty_state = state.State({})
        state_with_route0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        empty_state.merge_routes(state_with_route0)

        assert {
            Interface.KEY: [],
            Route.KEY: {Route.CONFIG: []},
        } == empty_state.state
        assert {} == empty_state.config_iface_routes

    def test_merge_iface_only_with_same_iface_routes_state(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        iface_only_state = state.State(
            {Interface.KEY: [{Interface.NAME: route0_obj.next_hop_interface}]}
        )
        state_with_route0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        iface_only_state.merge_routes(state_with_route0)

        expected = {
            Interface.KEY: [
                {
                    Interface.NAME: route0_obj.next_hop_interface,
                    Interface.IPV4: {},
                    Interface.IPV6: {},
                }
            ],
            Route.KEY: {Route.CONFIG: [route0]},
        }
        assert expected == iface_only_state.state
        assert {
            route0_obj.next_hop_interface: [route0_obj]
        } == iface_only_state.config_iface_routes

    def test_merge_iface_down_with_same_iface_routes_state(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        iface_down_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: route0_obj.next_hop_interface,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )
        state_with_route0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        iface_down_state.merge_routes(state_with_route0)

        expected = {
            Interface.KEY: [
                {
                    Interface.NAME: route0_obj.next_hop_interface,
                    Interface.STATE: InterfaceState.DOWN,
                    Interface.IPV4: {},
                    Interface.IPV6: {},
                }
            ],
            Route.KEY: {Route.CONFIG: []},
        }
        assert expected == iface_down_state.state
        assert {} == iface_down_state.config_iface_routes

    def test_merge_iface_ipv4_disabled_with_same_iface_routes_state(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        iface_down_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: route0_obj.next_hop_interface,
                        Interface.STATE: InterfaceState.UP,
                        Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                    }
                ]
            }
        )
        state_with_route0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        iface_down_state.merge_routes(state_with_route0)

        expected = {
            Interface.KEY: [
                {
                    Interface.NAME: route0_obj.next_hop_interface,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                    Interface.IPV6: {},
                }
            ],
            Route.KEY: {Route.CONFIG: []},
        }
        assert expected == iface_down_state.state
        assert {} == iface_down_state.config_iface_routes

    def test_merge_iface_ipv6_disabled_with_same_iface_routes_state(self):
        route1_obj = self._create_route1()
        route1 = route1_obj.to_dict()
        iface_down_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: route1_obj.next_hop_interface,
                        Interface.STATE: InterfaceState.UP,
                        Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                    }
                ]
            }
        )
        state_with_route1 = state.State({Route.KEY: {Route.CONFIG: [route1]}})

        iface_down_state.merge_routes(state_with_route1)

        expected = {
            Interface.KEY: [
                {
                    Interface.NAME: route1_obj.next_hop_interface,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {},
                    Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                }
            ],
            Route.KEY: {Route.CONFIG: []},
        }
        assert expected == iface_down_state.state
        assert {} == iface_down_state.config_iface_routes

    def test_merge_iface_ipv6_disabled_with_same_iface_ipv4_routes_state(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        iface_down_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: route0_obj.next_hop_interface,
                        Interface.STATE: InterfaceState.UP,
                        Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                    }
                ]
            }
        )
        state_with_route0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        iface_down_state.merge_routes(state_with_route0)

        expected = {
            Interface.KEY: [
                {
                    Interface.NAME: route0_obj.next_hop_interface,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {},
                    Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                }
            ],
            Route.KEY: {Route.CONFIG: [route0]},
        }
        assert expected == iface_down_state.state
        assert {
            route0_obj.next_hop_interface: [route0_obj]
        } == iface_down_state.config_iface_routes

    def test_merge_non_empty_with_empty_state(self):
        route0_obj = self._create_route0()
        route0 = route0_obj.to_dict()
        empty_state = state.State({})
        state_with_route0 = state.State({Route.KEY: {Route.CONFIG: [route0]}})

        state_with_route0.merge_routes(empty_state)

        assert {
            Interface.KEY: [],
            Route.KEY: {Route.CONFIG: [route0]},
        } == state_with_route0.state
        assert {"eth1": [route0_obj]} == state_with_route0.config_iface_routes

    def test_merge_absent_routes_with_no_matching(self):
        absent_route_obj = self._create_route0()
        absent_route_obj.state = Route.STATE_ABSENT
        absent_route = absent_route_obj.to_dict()
        other_route_obj = self._create_route1()
        other_route = other_route_obj.to_dict()
        s0 = state.State({Route.KEY: {Route.CONFIG: [absent_route]}})
        s1 = state.State({Route.KEY: {Route.CONFIG: [other_route]}})

        s0.merge_routes(s1)

        expected_state = {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}}
        assert expected_state == s0.state
        assert {} == s0.config_iface_routes

    def test_merge_absent_routes_with_matching(self):
        absent_route_obj = self._create_route0()
        absent_route_obj.state = Route.STATE_ABSENT
        absent_route = absent_route_obj.to_dict()
        other_route_obj = self._create_route0()
        other_route = other_route_obj.to_dict()
        s0 = state.State({Route.KEY: {Route.CONFIG: [absent_route]}})
        s1 = state.State({Route.KEY: {Route.CONFIG: [other_route]}})

        s0.merge_routes(s1)

        assert {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}} == s0.state
        assert {} == s0.config_iface_routes

    def _create_route0(self):
        return _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)

    def _create_route1(self):
        return _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )


def _create_route(dest, via_addr, via_iface, table, metric):
    return state.RouteEntry(
        _create_route_dict(dest, via_addr, via_iface, table, metric)
    )


def _create_route_dict(dest, via_addr, via_iface, table, metric):
    return {
        Route.DESTINATION: dest,
        Route.METRIC: metric,
        Route.NEXT_HOP_ADDRESS: via_addr,
        Route.NEXT_HOP_INTERFACE: via_iface,
        Route.TABLE_ID: table,
    }


def test_state_empty_routes():
    route_state = state.State({Route.KEY: {Route.CONFIG: []}})

    assert {} == route_state.config_iface_routes


def test_state_iface_routes_with_distinct_ifaces():
    routes = _get_mixed_test_routes()
    route_state = state.State({Route.KEY: {Route.CONFIG: routes}})
    expected_indexed_route_state = defaultdict(list)
    for route in routes:
        iface_name = route[Route.NEXT_HOP_INTERFACE]
        expected_indexed_route_state[iface_name].append(
            state.RouteEntry(route)
        )
        # No need to sort the routes as there is only 1 route per interface.

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_iface_routes_with_same_iface():
    routes = _get_mixed_test_routes()
    for route in routes:
        route[Route.NEXT_HOP_INTERFACE] = "eth1"
    route_state = state.State({Route.KEY: {Route.CONFIG: routes}})
    expected_indexed_route_state = {
        "eth1": sorted([state.RouteEntry(r) for r in routes])
    }

    assert expected_indexed_route_state == route_state.config_iface_routes


def test_state_iface_routes_order():
    # Changing all routes to eth1
    routes = _get_mixed_test_routes()
    for route in routes:
        route[Route.NEXT_HOP_INTERFACE] = "eth1"

    route_state = state.State(
        {Route.KEY: {Route.CONFIG: [routes[0], routes[1]]}}
    )
    reverse_route_state = state.State(
        {Route.KEY: {Route.CONFIG: [routes[1], routes[0]]}}
    )

    assert (
        route_state.config_iface_routes
        == reverse_route_state.config_iface_routes
    )


def test_state_verify_route_same():
    routes = _get_mixed_test_routes()
    route_state = state.State({Route.KEY: {Route.CONFIG: routes}})
    route_state_2 = state.State({Route.KEY: {Route.CONFIG: routes}})
    route_state.verify_routes(route_state_2)


def test_state_verify_route_diff_route_count():
    routes = _get_mixed_test_routes()
    route_state = state.State({Route.KEY: {Route.CONFIG: routes}})
    route_state_2 = state.State({Route.KEY: {Route.CONFIG: routes[:1]}})

    with pytest.raises(NmstateVerificationError):
        route_state.verify_routes(route_state_2)


def test_state_verify_route_diff_route_prop():
    routes = _get_mixed_test_routes()
    route_state = state.State({Route.KEY: {Route.CONFIG: routes}})
    routes[0][Route.NEXT_HOP_INTERFACE] = "another_nic"
    route_state_2 = state.State({Route.KEY: {Route.CONFIG: routes}})

    with pytest.raises(NmstateVerificationError):
        route_state.verify_routes(route_state_2)


def test_state_verify_route_empty():
    route_state = state.State({})
    route_state_2 = state.State({})
    route_state.verify_routes(route_state_2)


def _get_mixed_test_routes():
    r0 = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)
    r1 = _create_route("2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104)
    return [r0.to_dict(), r1.to_dict()]


def _gen_iface_states_for_routes(routes):
    ifaces = set([route[Route.NEXT_HOP_INTERFACE] for route in routes])
    return [
        {
            Interface.NAME: iface,
            Interface.STATE: InterfaceState.UP,
            Interface.IPV4: {InterfaceIPv4.ENABLED: True},
            Interface.IPV6: {InterfaceIPv6.ENABLED: True},
        }
        for iface in ifaces
    ]


def _route_sort_key(route):
    return (
        route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
        route.get(Route.NEXT_HOP_INTERFACE, ""),
        route.get(Route.DESTINATION, ""),
    )


class TestAssertDnsState:
    def test_merge_dns_empty_state_with_non_empty_state(self):
        dns_config = self._get_test_dns_config()
        current_state = state.State({DNS.KEY: dns_config})
        desire_state = state.State({})

        desire_state.merge_dns(current_state)

        assert current_state.config_dns == desire_state.config_dns

    def test_merge_dns_non_empty_state_with_empty_state(self):
        dns_config = self._get_test_dns_config()
        desire_state = state.State({DNS.KEY: dns_config})
        current_state = state.State({})

        desire_state.merge_dns(current_state)

        assert desire_state.config_dns == dns_config[DNS.CONFIG]

    def test_state_verify_dns_same(self):
        dns_config = self._get_test_dns_config()
        desire_state = state.State({DNS.KEY: dns_config})
        current_state = state.State({DNS.KEY: dns_config})

        desire_state.verify_dns(current_state)

    def test_verify_dns_same_entries_different_order(self):
        dns_config = self._get_test_dns_config()
        desire_state = state.State({DNS.KEY: dns_config})
        dns_config[DNS.CONFIG][DNS.SERVER].reverse()
        current_state = state.State(dns_config)

        with pytest.raises(NmstateVerificationError):
            desire_state.verify_dns(current_state)

    def test_state_verify_empty(self):
        desire_state = state.State({})
        current_state = state.State({})
        desire_state.verify_dns(current_state)

    def _get_test_dns_config(self):
        return {
            DNS.CONFIG: {
                DNS.SERVER: ["192.168.122.1", "2001:db8:a::1"],
                DNS.SEARCH: ["example.com", "example.org"],
            }
        }


class TestStateMatch:
    def test_match_empty_dict(self):
        assert state.state_match({}, {})

    def test_match_empty_list(self):
        assert state.state_match([], [])

    def test_match_none(self):
        assert state.state_match(None, None)

    def test_match_dict_vs_list(self):
        assert not state.state_match({}, [])

    def test_match_list_vs_string(self):
        assert not state.state_match(["a", "b", "c"], "abc")

    def test_match_dict_identical(self):
        assert state.state_match({"a": 1, "b": 2}, {"a": 1, "b": 2})

    def test_match_dict_current_has_more_data(self):
        assert state.state_match({"a": 1}, {"a": 1, "b": 2})

    def test_match_dict_desire_has_more_data(self):
        assert not state.state_match({"a": 1, "b": 2}, {"a": 1})

    def test_match_dict_different_value_type(self):
        assert not state.state_match({"a": 1, "b": []}, {"a": 1, "b": 2})

    def test_match_list_identical(self):
        assert state.state_match(["a", "b", 1], ["a", "b", 1])

    def test_match_list_different_order(self):
        assert not state.state_match(["a", "b", 1], ["a", 1, "b"])

    def test_match_list_current_contains_more(self):
        assert not state.state_match(["a", "b", 1], ["a", "b", "c", 1])

    def test_match_indentical_set(self):
        assert state.state_match(set(["a", "b", 1]), set(["a", "b", 1]))
        assert state.state_match(set(["a", 1, "b"]), set(["a", "b", 1]))
        assert state.state_match(set(["a", 1, 1, "b"]), set(["a", "b", 1]))

    def test_match_parital_set(self):
        assert not state.state_match(
            set(["a", "b", 1]), set(["a", "b", "c", 1])
        )

    def test_match_nested_list_in_dict(self):
        assert state.state_match({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]})

    def test_match_nested_dict_in_list(self):
        assert state.state_match(
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
        )
        assert state.state_match(
            [{"a": 1}, {"a": 2, "b": [3, 4]}],
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
        )
        assert not state.state_match(
            [{"a": 2, "b": [3, 4]}, {"a": 1, "b": [1, 2]}],
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
        )


class TestRouteRuleEntry:
    def test_hash_unique(self):
        rule = _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103)
        assert hash(rule) == hash(rule)

    def test_obj_unique(self):
        rule0 = _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103)
        rule1 = _create_route_rule("2001:db8:a::/64", "2001:db8:1::a", 51, 104)
        rule0_clone = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", 50, 103
        )
        assert rule0 == rule0_clone
        assert rule0 != rule1

    def test_obj_unique_without_table(self):
        rule_with_default_table_id = _create_route_rule(
            "198.51.100.0/24",
            "192.0.2.1",
            103,
            RouteRule.USE_DEFAULT_ROUTE_TABLE,
        )

        rule_without_table_id = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", 103, None
        )

        assert rule_without_table_id == rule_with_default_table_id

    def test_obj_unique_without_priority(self):
        rule_with_default_priority = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", RouteRule.USE_DEFAULT_PRIORITY, 50
        )

        rule_without_priority = _create_route_rule(
            "198.51.100.0/24", "192.0.2.1", None, 50
        )

        assert rule_without_priority == rule_with_default_priority

    def test_normal_object_as_dict(self):
        rule = _create_route_rule_dict("198.51.100.0/24", "192.0.2.1", 50, 103)
        rule_obj = state.RouteRuleEntry(rule)
        assert rule_obj.to_dict() == rule

    def test_sort_routes(self):
        rules = [
            _create_route_rule("198.51.100.1/24", "192.0.2.1", 50, 103),
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103),
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 10, 103),
        ]
        expected_rules = [
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 10, 103),
            _create_route_rule("198.51.100.0/24", "192.0.2.1", 50, 103),
            _create_route_rule("198.51.100.1/24", "192.0.2.1", 50, 103),
        ]
        assert expected_rules == sorted(rules)

    def test_verify_route_rules(self):
        self_state = state.State(
            {
                RouteRule.KEY: {
                    RouteRule.CONFIG: [
                        _create_route_rule_dict(
                            "198.51.100.1/24", "192.0.2.1", 50, 103
                        ),
                        _create_route_rule_dict(
                            "198.51.100.0/24", "192.0.2.1", 50, 103
                        ),
                        _create_route_rule_dict(
                            "198.51.100.0/24", "192.0.2.1", 10, 104
                        ),
                    ]
                }
            }
        )

        other_state = state.State(
            {
                RouteRule.KEY: {
                    RouteRule.CONFIG: [
                        _create_route_rule_dict(
                            "198.51.100.0/24", "192.0.2.1", 10, 104
                        ),
                        _create_route_rule_dict(
                            "198.51.100.1/24", "192.0.2.1", 50, 103
                        ),
                        _create_route_rule_dict(
                            "198.51.100.0/24", "192.0.2.1", 50, 103
                        ),
                    ]
                }
            }
        )
        self_state.verify_route_rule(other_state)


def _create_route_rule(ip_from, ip_to, priority, table):
    return state.RouteRuleEntry(
        _create_route_rule_dict(ip_from, ip_to, priority, table)
    )


def _create_route_rule_dict(ip_from, ip_to, priority, table):
    return {
        RouteRule.IP_FROM: ip_from,
        RouteRule.IP_TO: ip_to,
        RouteRule.PRIORITY: priority,
        RouteRule.ROUTE_TABLE: table,
    }


def test_remove_unknown_interfaces():
    desired_state = state.State(
        {
            Interface.KEY: [
                {Interface.NAME: "foo", Interface.TYPE: InterfaceType.UNKNOWN}
            ]
        }
    )

    desired_state.remove_unknown_interfaces()
    assert not desired_state.interfaces
