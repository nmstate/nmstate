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

import pytest

from libnmstate import state, metadata
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge


PORT0 = "eth0"
PORT1 = "eth1"
BOND0 = "bond0"

OVS_NAME = "ovs-br99"
TYPE_OVS_BR = InterfaceType.OVS_BRIDGE


@pytest.mark.parametrize("bonded", [False, True], ids=("not-bonded", "bonded"))
class TestDesiredStateOvsMetadata:
    def test_ovs_creation_with_new_ports(self, bonded):
        if bonded:
            ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        ports_state = {OVSBridge.PORT_SUBTREE: ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: ports_state,
                    },
                    {
                        Interface.NAME: PORT0,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        current_state = state.State({})
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces[PORT0][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT1][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT0][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces[PORT1][metadata.MASTER_TYPE] = TYPE_OVS_BR
        desired_p0 = _get_bridge_port_state(desired_state, OVS_NAME, 0)
        expected_dstate.interfaces[PORT0][metadata.BRPORT_OPTIONS] = desired_p0
        if bonded:
            desired_p1 = desired_p0
        else:
            desired_p1 = _get_bridge_port_state(desired_state, OVS_NAME, 1)
        expected_dstate.interfaces[PORT1][metadata.BRPORT_OPTIONS] = desired_p1

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_creation_with_existing_ports(self, bonded):
        if bonded:
            ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        ports_state = {OVSBridge.PORT_SUBTREE: ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: ports_state,
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: PORT0,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces[PORT0] = {
            Interface.NAME: PORT0,
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces[PORT0][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT0][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces[PORT1] = {
            Interface.NAME: PORT1,
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces[PORT1][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT1][metadata.MASTER_TYPE] = TYPE_OVS_BR
        desired_p0 = _get_bridge_port_state(desired_state, OVS_NAME, 0)
        expected_dstate.interfaces[PORT0][metadata.BRPORT_OPTIONS] = desired_p0
        if bonded:
            desired_p1 = desired_p0
        else:
            desired_p1 = _get_bridge_port_state(desired_state, OVS_NAME, 1)
        expected_dstate.interfaces[PORT1][metadata.BRPORT_OPTIONS] = desired_p1

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_editing_option(self, bonded):
        if bonded:
            ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        ports_state = {OVSBridge.PORT_SUBTREE: ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: ports_state,
                    },
                    {
                        Interface.NAME: PORT0,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_adding_slaves(self, bonded):
        if bonded:
            ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        ports_state = {OVSBridge.PORT_SUBTREE: ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: ports_state,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: PORT0,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    }
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces[PORT0] = {
            Interface.NAME: PORT0,
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces[PORT0][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT1][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT0][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces[PORT1][metadata.MASTER_TYPE] = TYPE_OVS_BR
        desired_p0 = _get_bridge_port_state(desired_state, OVS_NAME, 0)
        expected_dstate.interfaces[PORT0][metadata.BRPORT_OPTIONS] = desired_p0
        if bonded:
            desired_p1 = desired_p0
        else:
            desired_p1 = _get_bridge_port_state(desired_state, OVS_NAME, 1)
        expected_dstate.interfaces[PORT1][metadata.BRPORT_OPTIONS] = desired_p1

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_removing_slaves(self, bonded):
        if bonded:
            desired_ports = [_create_lag_port_state((PORT0,))]
            current_ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            desired_ports = [{OVSBridge.Port.NAME: PORT0}]
            current_ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        desired_ports_state = {OVSBridge.PORT_SUBTREE: desired_ports}
        current_ports_state = {OVSBridge.PORT_SUBTREE: current_ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: desired_ports_state,
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: current_ports_state,
                    },
                    {
                        Interface.NAME: PORT0,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.ETHERNET,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.ETHERNET,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces[PORT0] = {
            Interface.NAME: PORT0,
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces[PORT0][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT0][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces[PORT1] = {Interface.NAME: PORT1}
        desired_p0 = _get_bridge_port_state(desired_state, OVS_NAME, 0)
        expected_dstate.interfaces[PORT0][metadata.BRPORT_OPTIONS] = desired_p0

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_edit_slave(self, bonded):
        if bonded:
            ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        ports_state = {OVSBridge.PORT_SUBTREE: ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: PORT0,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                        "fookey": "fooval",
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: ports_state,
                    },
                    {
                        Interface.NAME: PORT0,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces[PORT0][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces[PORT0][metadata.MASTER_TYPE] = TYPE_OVS_BR
        current_p0 = _get_bridge_port_state(current_state, OVS_NAME, 0)
        expected_dstate.interfaces[PORT0][metadata.BRPORT_OPTIONS] = current_p0

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_reusing_slave_used_by_existing_bridge(self, bonded):
        OVS2_NAME = "ovs-br88"
        if bonded:
            desired_ports = [_create_lag_port_state((PORT0,))]
            current_ports = [_create_lag_port_state((PORT0, PORT1))]
        else:
            desired_ports = [{OVSBridge.Port.NAME: PORT0}]
            current_ports = [
                {OVSBridge.Port.NAME: PORT0},
                {OVSBridge.Port.NAME: PORT1},
            ]
        desired_ports_state = {OVSBridge.PORT_SUBTREE: desired_ports}
        current_ports_state = {OVSBridge.PORT_SUBTREE: current_ports}

        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS2_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: desired_ports_state,
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: OVS_NAME,
                        Interface.TYPE: TYPE_OVS_BR,
                        Interface.STATE: InterfaceState.UP,
                        OVSBridge.CONFIG_SUBTREE: current_ports_state,
                    },
                    {
                        Interface.NAME: PORT0,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: PORT1,
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces[PORT0] = {
            Interface.NAME: PORT0,
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces[PORT0][metadata.MASTER] = OVS2_NAME
        expected_dstate.interfaces[PORT0][metadata.MASTER_TYPE] = TYPE_OVS_BR
        desired_p0 = _get_bridge_port_state(desired_state, OVS2_NAME, 0)
        expected_dstate.interfaces[PORT0][metadata.BRPORT_OPTIONS] = desired_p0

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate


def _create_lag_port_state(slaves):
    return {
        OVSBridge.Port.NAME: BOND0,
        OVSBridge.Port.LINK_AGGREGATION_SUBTREE: {
            OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE: [
                {OVSBridge.Port.LinkAggregation.Slave.NAME: slave}
                for slave in slaves
            ]
        },
    }


def _get_bridge_port_state(desired_state, bridge_name, port_index):
    brconfig = desired_state.interfaces[bridge_name][OVSBridge.CONFIG_SUBTREE]
    return brconfig[OVSBridge.PORT_SUBTREE][port_index]
