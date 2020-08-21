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


from libnmstate.ifaces import NmstateLinuxBridgePortVlan
from libnmstate.ifaces import KernelBridgePortVlans


def get_port_vlan_info(np_sub):
    return NmstateLinuxBridgePortVlan.new_from_kernel_vlans(
        [_np_vlan_to_kernel_vlan(np_vlan) for np_vlan in np_sub.vlans]
    ).to_dict()


def _np_vlan_to_kernel_vlan(np_vlan):
    if np_vlan.vid_range:
        vid_min, vid_max = np_vlan.vid_range
    else:
        vid_min = vid_max = np_vlan.vid
    return KernelBridgePortVlans(
        vid_min, vid_max, np_vlan.is_pvid, np_vlan.is_egress_untagged
    )
