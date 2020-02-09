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

import pytest

import libnmstate
from libnmstate import schema
from libnmstate import state
from libnmstate import validator
from libnmstate.schema import DNS
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import VXLAN
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError


class TestLinkAggregationState:
    def test_bonds_with_no_slaves(self):
        desired_state = state.State(
            {
                schema.Interface.KEY: [
                    {"name": "bond0", "link-aggregation": {"slaves": []}},
                    {"name": "bond1", "link-aggregation": {"slaves": []}},
                ]
            }
        )

        libnmstate.validator.validate_link_aggregation_state(
            desired_state, empty_state()
        )

    def test_bonds_with_single_slave(self):
        desired_state = state.State(
            {
                schema.Interface.KEY: [
                    {"name": "slave0"},
                    {"name": "slave1"},
                    {
                        "name": "bond0",
                        "link-aggregation": {"slaves": ["slave0"]},
                    },
                    {
                        "name": "bond1",
                        "link-aggregation": {"slaves": ["slave1"]},
                    },
                ]
            }
        )
        libnmstate.validator.validate_link_aggregation_state(
            desired_state, empty_state()
        )

    def test_bonds_with_multiple_slaves(self):
        desired_state = state.State(
            {
                schema.Interface.KEY: [
                    {"name": "slave0"},
                    {"name": "slave1"},
                    {"name": "slave00"},
                    {"name": "slave11"},
                    {
                        "name": "bond0",
                        "link-aggregation": {"slaves": ["slave0", "slave00"]},
                    },
                    {
                        "name": "bond1",
                        "link-aggregation": {"slaves": ["slave1", "slave11"]},
                    },
                ]
            }
        )
        libnmstate.validator.validate_link_aggregation_state(
            desired_state, empty_state()
        )

    def test_bonds_with_multiple_slaves_reused(self):
        desired_state = state.State(
            {
                schema.Interface.KEY: [
                    {"name": "slave0"},
                    {"name": "slave1"},
                    {"name": "slave00"},
                    {
                        "name": "bond0",
                        "link-aggregation": {"slaves": ["slave0", "slave00"]},
                    },
                    {
                        "name": "bond1",
                        "link-aggregation": {"slaves": ["slave1", "slave00"]},
                    },
                ]
            }
        )
        with pytest.raises(NmstateValueError):
            libnmstate.validator.validate_link_aggregation_state(
                desired_state, empty_state()
            )

    def test_bonds_with_missing_slaves(self):
        desired_state = state.State(
            {
                schema.Interface.KEY: [
                    {"name": "slave0"},
                    {"name": "slave1"},
                    {
                        "name": "bond0",
                        "link-aggregation": {"slaves": ["slave0", "slave00"]},
                    },
                    {
                        "name": "bond1",
                        "link-aggregation": {"slaves": ["slave1", "slave11"]},
                    },
                ]
            }
        )
        with pytest.raises(NmstateValueError):
            libnmstate.validator.validate_link_aggregation_state(
                desired_state, empty_state()
            )


@pytest.mark.xfail(
    raises=NmstateNotImplementedError,
    reason="https://nmstate.atlassian.net/browse/NMSTATE-220",
    strict=True,
)
def test_dns_three_nameservers():
    libnmstate.validator.validate_dns(
        {
            DNS.KEY: {
                DNS.CONFIG: {
                    DNS.SERVER: ["8.8.8.8", "2001:4860:4860::8888", "8.8.4.4"]
                }
            }
        }
    )


def test_unique_interface_name():
    with pytest.raises(validator.NmstateDuplicateInterfaceNameError):
        libnmstate.validator.validate_unique_interface_name(
            {
                schema.Interface.KEY: [
                    {schema.Interface.NAME: "foo0"},
                    {schema.Interface.NAME: "foo0"},
                ]
            }
        )


def empty_state():
    return state.State({})


class TestRouteValidation:
    def test_empty_states(self):
        validator.validate_routes(state.State({}), state.State({}))

    def test_valid_route_based_on_desired_state(self):
        iface0 = _create_interface_state("eth1", ipv4=True)
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [iface0],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )

        validator.validate_routes(desired_state, state.State({}))

    def test_valid_route_based_on_current_state(self):
        iface0 = _create_interface_state("eth1", ipv4=True)
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )
        current_state = state.State(
            {
                schema.Interface.KEY: [iface0],
                schema.Route.KEY: {schema.Route.CONFIG: []},
            }
        )

        validator.validate_routes(desired_state, current_state)

    def test_invalid_route_due_to_missing_iface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )

        with pytest.raises(validator.NmstateRouteWithNoInterfaceError):
            validator.validate_routes(desired_state, state.State({}))

    def test_invalid_route_due_to_non_up_iface(self):
        iface0 = _create_interface_state(
            "eth1", state=schema.InterfaceState.DOWN, ipv4=True
        )
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [iface0],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )
        with pytest.raises(validator.NmstateRouteWithNoUpInterfaceError):
            validator.validate_routes(desired_state, state.State({}))

    def test_invalid_route_due_to_missing_ipv4(self):
        iface0 = _create_interface_state("eth1", ipv4=False)
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [iface0],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )
        with pytest.raises(validator.NmstateRouteWithNoIPInterfaceError):
            validator.validate_routes(desired_state, state.State({}))

    def test_invalid_route_due_to_missing_ipv6(self):
        iface1 = _create_interface_state("eth2", ipv6=False)
        route1 = self._create_route1()
        desired_state = state.State(
            {
                schema.Interface.KEY: [iface1],
                schema.Route.KEY: {schema.Route.CONFIG: [route1]},
            }
        )
        with pytest.raises(validator.NmstateRouteWithNoIPInterfaceError):
            validator.validate_routes(desired_state, state.State({}))

    def test_valid_route_based_on_desired_state_but_not_current(self):
        iface0 = _create_interface_state("eth1", ipv4=True)
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [iface0],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )
        iface0_down = _create_interface_state(
            "eth1", state=schema.InterfaceState.DOWN
        )
        current_state = state.State(
            {
                schema.Interface.KEY: [iface0_down],
                schema.Route.KEY: {schema.Route.CONFIG: []},
            }
        )

        validator.validate_routes(desired_state, current_state)

    def test_invalid_route_based_on_desired_state_but_not_current(self):
        iface0_ipv4_disabled = _create_interface_state("eth1", ipv4=False)
        route0 = self._create_route0()
        desired_state = state.State(
            {
                schema.Interface.KEY: [iface0_ipv4_disabled],
                schema.Route.KEY: {schema.Route.CONFIG: [route0]},
            }
        )
        iface0_ipv4_enabled = _create_interface_state("eth1", ipv4=True)
        current_state = state.State(
            {
                schema.Interface.KEY: [iface0_ipv4_enabled],
                schema.Route.KEY: {schema.Route.CONFIG: []},
            }
        )

        with pytest.raises(validator.NmstateRouteWithNoIPInterfaceError):
            validator.validate_routes(desired_state, current_state)

    def _create_route0(self):
        return _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)

    def _create_route1(self):
        return _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )


class TestVxlanValidation:

    parametrize_vxlan_req_fields = pytest.mark.parametrize(
        "required_field", [VXLAN.ID, VXLAN.REMOTE, VXLAN.BASE_IFACE]
    )

    @parametrize_vxlan_req_fields
    def test_missing_requiered_field_is_invalid(self, required_field):
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: "eth0.101",
                    schema.Interface.TYPE: VXLAN.TYPE,
                    VXLAN.CONFIG_SUBTREE: {
                        VXLAN.ID: 99,
                        VXLAN.REMOTE: "192.168.3.3",
                        VXLAN.BASE_IFACE: "eth0",
                    },
                }
            ]
        }

        desired_state[schema.Interface.KEY][0][VXLAN.CONFIG_SUBTREE].pop(
            required_field
        )

        with pytest.raises(NmstateValueError) as err:
            libnmstate.validator.validate_vxlan(desired_state)

        assert required_field in err.value.args[0]

    def test_minimal_config_is_valid(self):
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: "eth0.101",
                    schema.Interface.TYPE: VXLAN.TYPE,
                    VXLAN.CONFIG_SUBTREE: {
                        VXLAN.ID: 99,
                        VXLAN.REMOTE: "192.168.3.3",
                        VXLAN.BASE_IFACE: "eth0",
                    },
                }
            ]
        }
        libnmstate.validator.validate_vxlan(desired_state)


class TestVlanFilteringValidation:
    def test_access_port_cant_have_trunks(self):
        invalid_vlan_config = {
            LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.ACCESS,
            LB.Port.Vlan.TRUNK_TAGS: [
                {
                    LB.Port.Vlan.TrunkTags.ID_RANGE: {
                        LB.Port.Vlan.TrunkTags.MIN_RANGE: 200,
                        LB.Port.Vlan.TrunkTags.MAX_RANGE: 299,
                    }
                }
            ],
        }
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: "br0",
                    schema.Interface.TYPE: LB.TYPE,
                    schema.Interface.STATE: schema.InterfaceState.UP,
                    LB.PORT_SUBTREE: [
                        {
                            LB.Port.NAME: "eth1",
                            LB.Port.VLAN_SUBTREE: invalid_vlan_config,
                        }
                    ],
                }
            ]
        }
        with pytest.raises(
            NmstateValueError, match="Access port cannot have trunk tags"
        ):
            libnmstate.validator.validate_bridge(desired_state)

    def test_trunk_port_must_have_at_least_1_tag(self):
        invalid_vlan_config = {
            LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
            LB.Port.Vlan.TRUNK_TAGS: [],
        }
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: "br0",
                    schema.Interface.TYPE: LB.TYPE,
                    schema.Interface.STATE: schema.InterfaceState.UP,
                    LB.PORT_SUBTREE: [
                        {
                            LB.Port.NAME: "eth1",
                            LB.Port.VLAN_SUBTREE: invalid_vlan_config,
                        }
                    ],
                }
            ]
        }
        with pytest.raises(
            NmstateValueError,
            match="A trunk port needs to specify trunk tags",
        ):
            libnmstate.validator.validate_bridge(desired_state)

    def test_specify_both_vlan_id_and_id_range_is_invalid(self):
        invalid_vlan_config = {
            LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
            LB.Port.Vlan.TRUNK_TAGS: [
                {
                    LB.Port.Vlan.TrunkTags.ID: 101,
                    LB.Port.Vlan.TrunkTags.ID_RANGE: {
                        LB.Port.Vlan.TrunkTags.MIN_RANGE: 200,
                        LB.Port.Vlan.TrunkTags.MAX_RANGE: 299,
                    },
                }
            ],
        }
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: "br0",
                    schema.Interface.TYPE: LB.TYPE,
                    schema.Interface.STATE: schema.InterfaceState.UP,
                    LB.PORT_SUBTREE: [
                        {
                            LB.Port.NAME: "eth1",
                            LB.Port.VLAN_SUBTREE: invalid_vlan_config,
                        }
                    ],
                }
            ]
        }
        with pytest.raises(NmstateValueError) as err:
            libnmstate.validator.validate_bridge(desired_state)
        assert (
            "Trunk port cannot be configured by both id and range"
            in err.value.args[0]
        )

    @pytest.mark.parametrize(
        "range_key",
        [LB.Port.Vlan.TrunkTags.MIN_RANGE, LB.Port.Vlan.TrunkTags.MAX_RANGE],
        ids=["only_min", "only_max"],
    )
    def test_vlan_ranges_must_have_min_and_max(self, range_key):
        vlan_tag = 101
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: "br0",
                    schema.Interface.TYPE: LB.TYPE,
                    schema.Interface.STATE: schema.InterfaceState.UP,
                    LB.PORT_SUBTREE: [
                        {
                            LB.Port.NAME: "eth1",
                            LB.Port.VLAN_SUBTREE: {
                                LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
                                LB.Port.Vlan.TRUNK_TAGS: [
                                    {
                                        LB.Port.Vlan.TrunkTags.ID_RANGE: {
                                            range_key: vlan_tag
                                        }
                                    }
                                ],
                            },
                        }
                    ],
                }
            ]
        }
        with pytest.raises(NmstateValueError) as err:
            libnmstate.validator.validate_bridge(desired_state)
        assert "Trunk port range requires min / max keys" in err.value.args[0]


def _create_interface_state(
    iface_name, state=schema.InterfaceState.UP, ipv4=True, ipv6=True
):
    return {
        schema.Interface.NAME: iface_name,
        schema.Interface.TYPE: schema.InterfaceType.ETHERNET,
        schema.Interface.STATE: state,
        schema.Interface.IPV4: {InterfaceIPv4.ENABLED: ipv4},
        schema.Interface.IPV6: {InterfaceIPv6.ENABLED: ipv6},
    }


def _create_route(dest, via_addr, via_iface, table, metric):
    return {
        schema.Route.DESTINATION: dest,
        schema.Route.METRIC: metric,
        schema.Route.NEXT_HOP_ADDRESS: via_addr,
        schema.Route.NEXT_HOP_INTERFACE: via_iface,
        schema.Route.TABLE_ID: table,
    }
