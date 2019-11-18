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


from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB


BRIDGE_ENABLE_VLAN_FILTERING = "_enable_vlan_filtering"


def get_slaves_from_state(state, default=()):
    ports = state.get("bridge", {}).get("port")
    if ports is None:
        return default
    return [p["name"] for p in ports]


def set_bridge_ports_metadata(master_state, slave_state):
    ports = master_state.get("bridge", {}).get("port", [])
    port = next(filter(lambda n: n["name"] == slave_state["name"], ports), {})
    slave_state["_brport_options"] = port


def generate_port_vlan_metadata(desired_state, current_state):
    desired_bridges = _filter_interface_type(
        desired_state.interfaces, InterfaceType.LINUX_BRIDGE
    )
    current_bridges = _filter_interface_type(
        current_state.interfaces, InterfaceType.LINUX_BRIDGE
    )
    desired_port_vlan_status_per_bridge = _get_port_vlan_status(
        desired_bridges
    )
    current_port_vlan_status_per_bridge = _get_port_vlan_status(
        current_bridges
    )

    for brname, brstate in desired_bridges.items():
        desired_port_vlan_status = desired_port_vlan_status_per_bridge.get(
            brname, {}
        )
        current_port_vlan_status = current_port_vlan_status_per_bridge.get(
            brname, {}
        )
        current_port_vlan_status.update(desired_port_vlan_status)
        enable_vlan_filtering = any(current_port_vlan_status.values())
        brstate[BRIDGE_ENABLE_VLAN_FILTERING] = enable_vlan_filtering


def _get_port_vlan_status(bridges):
    port_vlan_status = {}
    for bridge_name, bridge_state in bridges.items():
        port_vlan_status[bridge_name] = {}
        bridge_config = bridge_state.get(LB.CONFIG_SUBTREE, {})
        for port in bridge_config.get(LB.PORT_SUBTREE, []):
            port_name = port[LB.Port.NAME]
            bridge_port_vlan_status = port_vlan_status[bridge_name]
            port_vlan_enabled = LB.Port.VLAN_SUBTREE in port
            bridge_port_vlan_status[port_name] = port_vlan_enabled
    return port_vlan_status


def _filter_interface_type(interfaces, interface_type):
    return {
        if_name: if_state
        for if_name, if_state in interfaces.items()
        if if_state.get(Interface.TYPE) == interface_type
        and if_state.get(Interface.STATE) == InterfaceState.UP
    }
