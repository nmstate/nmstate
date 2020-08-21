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

from libnmstate.ifaces import NmstateLinuxBridgePortVlan

from .common import NM


def nmstate_port_vlan_to_nm(nmstate_vlan_config):
    nm_vlans = []
    nmstate_port_vlan = NmstateLinuxBridgePortVlan(nmstate_vlan_config)
    for kernel_vlan in nmstate_port_vlan.to_kernel_vlans():
        nm_vlan = NM.BridgeVlan.new(kernel_vlan.vid_min, kernel_vlan.vid_max)
        nm_vlan.set_untagged(kernel_vlan.is_egress_untagged)
        nm_vlan.set_pvid(kernel_vlan.is_pvid)
        nm_vlans.append(nm_vlan)
    return nm_vlans
