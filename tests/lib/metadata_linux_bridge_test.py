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

from libnmstate import metadata
from libnmstate import state
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge

from .testlib.portvlanlib import generate_vlan_filtering_config
from .testlib.portvlanlib import generate_vlan_id_config
from .testlib.portvlanlib import update_bridge_port_vlan_config

BRIDGE0 = "br0"
BRIDGE1 = "br1"
IFACE0 = "eth0"
IFACE1 = "eth1"


class TestLinuxBridgeMetadata:
    def test_creation_with_new_ports(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0, IFACE1)),
                    _create_iface_state(IFACE0, InterfaceType.UNKNOWN),
                    _create_iface_state(IFACE1, InterfaceType.UNKNOWN),
                ]
            }
        )
        current_state = state.State({})
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE0,
                        (IFACE0, IFACE1),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(
                        IFACE0,
                        InterfaceType.UNKNOWN,
                        extra=_create_metadata_state(BRIDGE0, IFACE0),
                    ),
                    _create_iface_state(
                        IFACE1,
                        InterfaceType.UNKNOWN,
                        extra=_create_metadata_state(BRIDGE0, IFACE1),
                    ),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_creation_with_existing_ports(self):
        desired_state = state.State(
            {Interface.KEY: [_create_bridge_state(BRIDGE0, (IFACE0, IFACE1))]}
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_iface_state(
                        IFACE0, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                    _create_iface_state(
                        IFACE1, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                ]
            }
        )
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE0,
                        (IFACE0, IFACE1),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(
                        IFACE0,
                        ifstate=InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE0, IFACE0),
                    ),
                    _create_iface_state(
                        IFACE1,
                        ifstate=InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE0, IFACE1),
                    ),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_removing_birdge(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    _create_iface_state(
                        BRIDGE0,
                        InterfaceType.LINUX_BRIDGE,
                        InterfaceState.DOWN,
                    ),
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0, IFACE1)),
                    _create_iface_state(IFACE0, InterfaceType.UNKNOWN),
                    _create_iface_state(IFACE1, InterfaceType.UNKNOWN),
                ]
            }
        )
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_desired_state
        assert current_state == expected_current_state

    def test_adding_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0, IFACE1)),
                    _create_iface_state(
                        IFACE1, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0,)),
                    _create_iface_state(
                        IFACE0, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                ]
            }
        )
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE0,
                        (IFACE0, IFACE1),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(
                        IFACE1,
                        InterfaceType.UNKNOWN,
                        InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE0, IFACE1),
                    ),
                    _create_iface_state(
                        IFACE0,
                        ifstate=InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE0, IFACE0),
                    ),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_removing_slave(self):
        desired_state = state.State(
            {Interface.KEY: [_create_bridge_state(BRIDGE0, (IFACE0,))]}
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0, IFACE1)),
                    _create_iface_state(
                        IFACE0, InterfaceType.ETHERNET, InterfaceState.UP
                    ),
                    _create_iface_state(
                        IFACE1, InterfaceType.ETHERNET, InterfaceState.UP
                    ),
                ]
            }
        )
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE0,
                        (IFACE0,),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(
                        IFACE0,
                        ifstate=InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE0, IFACE0),
                    ),
                    _create_iface_state(IFACE1),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_edit_bridge_with_unmanaged_slave(self):
        desired_state = state.State(
            {Interface.KEY: [_create_bridge_state(BRIDGE0, (IFACE0,))]}
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0, IFACE1)),
                    _create_iface_state(
                        IFACE0, InterfaceType.ETHERNET, InterfaceState.UP
                    ),
                    _create_iface_state(
                        IFACE1, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                ]
            }
        )
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE0,
                        (IFACE0,),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(
                        IFACE0,
                        ifstate=InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE0, IFACE0),
                    ),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_edit_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    _create_iface_state(
                        IFACE0,
                        InterfaceType.UNKNOWN,
                        extra={"fookey": "fooval"},
                    ),
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE0,
                        (IFACE0, IFACE1),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(IFACE0, InterfaceType.UNKNOWN),
                    _create_iface_state(IFACE1, InterfaceType.UNKNOWN),
                ]
            }
        )
        extra_iface0_state = _create_metadata_state(BRIDGE0, IFACE0)
        extra_iface0_state["fookey"] = "fooval"
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_iface_state(
                        IFACE0,
                        InterfaceType.UNKNOWN,
                        extra=extra_iface0_state,
                    ),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_reusing_slave_used_by_existing_bridge(self):
        desired_state = state.State(
            {Interface.KEY: [_create_bridge_state(BRIDGE1, (IFACE0,))]}
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(BRIDGE0, (IFACE0, IFACE1)),
                    _create_iface_state(
                        IFACE0, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                    _create_iface_state(
                        IFACE1, InterfaceType.UNKNOWN, InterfaceState.UP
                    ),
                ]
            }
        )
        expected_dstate = state.State(
            {
                Interface.KEY: [
                    _create_bridge_state(
                        BRIDGE1,
                        (IFACE0,),
                        extra=_create_bridge_metadata_state(
                            vlan_filtering=False
                        ),
                    ),
                    _create_iface_state(
                        IFACE0,
                        ifstate=InterfaceState.UP,
                        extra=_create_metadata_state(BRIDGE1, IFACE0),
                    ),
                ]
            }
        )
        expected_cstate = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate
        assert current_state == expected_cstate

    def test_port_vlan_metadata_create(self):
        bridge = _create_bridge_state(BRIDGE1, (IFACE0,))
        update_bridge_port_vlan_config(
            bridge,
            IFACE0,
            generate_vlan_filtering_config(
                LinuxBridge.Port.Vlan.Mode.TRUNK,
                generate_vlan_id_config(100, 200, 300),
            ),
        )
        desired_state = state.State({Interface.KEY: [bridge]})
        current_state = state.State({})

        expected_bridge_state = copy.deepcopy(bridge)
        expected_bridge_state.update(
            _create_bridge_metadata_state(vlan_filtering=True)
        )
        expected_dstate = state.State({Interface.KEY: [expected_bridge_state]})

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert state.State(desired_state.state) == expected_dstate

    def test_port_vlan_metadata_update_keep_vlan_filtering_enabled(self):
        bridge = _create_bridge_state(BRIDGE1, (IFACE0, IFACE1))
        update_bridge_port_vlan_config(
            bridge,
            IFACE0,
            generate_vlan_filtering_config(
                LinuxBridge.Port.Vlan.Mode.TRUNK,
                generate_vlan_id_config(100, 200, 300),
            ),
        )

        current_bridge = copy.deepcopy(bridge)
        update_bridge_port_vlan_config(
            current_bridge,
            IFACE1,
            generate_vlan_filtering_config(
                LinuxBridge.Port.Vlan.Mode.TRUNK, generate_vlan_id_config(500),
            ),
        )
        desired_state = state.State({Interface.KEY: [bridge]})
        current_state = state.State({Interface.KEY: [current_bridge]})

        expected_desired_bridge_state = copy.deepcopy(bridge)
        expected_desired_bridge_state.update(
            _create_bridge_metadata_state(vlan_filtering=True)
        )
        expected_dstate = state.State(
            {Interface.KEY: [expected_desired_bridge_state]}
        )

        metadata.generate_ifaces_metadata(desired_state, current_state)
        assert state.State(desired_state.state) == expected_dstate

    def test_port_vlan_metadata_update_disable_vlan_filtering(self):
        bridge = _create_bridge_state(BRIDGE1, (IFACE0, IFACE1))
        current_bridge = copy.deepcopy(bridge)

        update_bridge_port_vlan_config(
            current_bridge,
            IFACE0,
            generate_vlan_filtering_config(
                LinuxBridge.Port.Vlan.Mode.TRUNK,
                generate_vlan_id_config(100, 200, 300),
            ),
        )

        desired_state = state.State({Interface.KEY: [bridge]})
        current_state = state.State({Interface.KEY: [current_bridge]})

        expected_desired_bridge_state = copy.deepcopy(bridge)
        expected_desired_bridge_state.update(
            _create_bridge_metadata_state(vlan_filtering=False)
        )
        expected_dstate = state.State(
            {Interface.KEY: [expected_desired_bridge_state]}
        )

        metadata.generate_ifaces_metadata(desired_state, current_state)
        assert state.State(desired_state.state) == expected_dstate


def _create_bridge_state(bridge_name, ports_names, extra=None):
    bridge_state = {
        Interface.NAME: bridge_name,
        Interface.TYPE: InterfaceType.LINUX_BRIDGE,
        Interface.STATE: InterfaceState.UP,
        LinuxBridge.CONFIG_SUBTREE: {
            LinuxBridge.PORT_SUBTREE: [
                {LinuxBridge.Port.NAME: port_name} for port_name in ports_names
            ]
        },
    }

    if extra:
        bridge_state.update(extra)
    return bridge_state


def _create_iface_state(ifname, iftype=None, ifstate=None, extra=None):
    iface_state = {Interface.NAME: ifname}
    if iftype:
        iface_state[Interface.TYPE] = iftype
    if ifstate:
        iface_state[Interface.STATE] = ifstate
    if extra:
        iface_state.update(extra)
    return iface_state


def _create_metadata_state(bridge_name, port_name):
    return {
        metadata.MASTER: bridge_name,
        metadata.MASTER_TYPE: InterfaceType.LINUX_BRIDGE,
        metadata.BRPORT_OPTIONS: {LinuxBridge.Port.NAME: port_name},
    }


def _create_bridge_metadata_state(vlan_filtering):
    return {metadata.BRIDGE_ENABLE_VLAN_FILTERING: vlan_filtering}
