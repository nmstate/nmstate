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

from libnmstate.schema import LinuxBridge


def update_bridge_port_vlan_config(bridge, port_name, vlan_config):
    port_subtree = bridge[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE]
    port = next((port for port in port_subtree if port["name"] == port_name))

    port[LinuxBridge.Port.VLAN_SUBTREE] = vlan_config


def generate_vlan_filtering_config(
    port_type, trunk_tags=None, tag=None, native_vlan=None
):
    vlan_filtering_state = {
        LinuxBridge.Port.Vlan.MODE: port_type,
        LinuxBridge.Port.Vlan.TRUNK_TAGS: trunk_tags or [],
    }

    if tag:
        vlan_filtering_state[LinuxBridge.Port.Vlan.TAG] = tag
    if native_vlan is not None:
        vlan_filtering_state[LinuxBridge.Port.Vlan.ENABLE_NATIVE] = native_vlan

    return {LinuxBridge.Port.VLAN_SUBTREE: vlan_filtering_state}


def generate_vlan_id_config(*vlan_ids):
    return [
        {LinuxBridge.Port.Vlan.TrunkTags.ID: vlan_id} for vlan_id in vlan_ids
    ]


def generate_vlan_id_range_config(min_vlan_id, max_vlan_id):
    return {
        LinuxBridge.Port.Vlan.TrunkTags.ID_RANGE: {
            LinuxBridge.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan_id,
            LinuxBridge.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan_id,
        }
    }
