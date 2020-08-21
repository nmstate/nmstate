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

from operator import itemgetter

from libnmstate.schema import LinuxBridge as LB


class KernelBridgePortVlans:
    def __init__(
        self,
        vid_min=None,
        vid_max=None,
        is_pvid=False,
        is_egress_untagged=False,
    ):
        self.vid_min = vid_min
        self.vid_max = vid_max
        self.is_pvid = is_pvid
        self.is_egress_untagged = is_egress_untagged

    def get_vlan_tag_range(self):
        return (self.vid_min, self.vid_max)

    def to_dict(self):
        if self.vid_min != self.vid_max:
            return {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: self.vid_min,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: self.vid_max,
                }
            }
        else:
            return {LB.Port.Vlan.TrunkTags.ID: self.vid_min}


class NmstateLinuxBridgePortVlan:
    def __init__(self, info):
        self._is_native = info.get(LB.Port.Vlan.ENABLE_NATIVE, False)
        self._trunk_tags = info.get(LB.Port.Vlan.TRUNK_TAGS, [])
        self._tag = info.get(LB.Port.Vlan.TAG, None)
        self._mode = info.get(LB.Port.Vlan.MODE, LB.Port.Vlan.Mode.ACCESS)

    @staticmethod
    def new_from_kernel_vlans(kernel_vlans):
        obj = NmstateLinuxBridgePortVlan({})
        obj._is_native = False
        trunk_tags = []

        is_access_port = NmstateLinuxBridgePortVlan._is_access_port(
            kernel_vlans
        )
        for kernel_vlan in kernel_vlans:
            vlan_min, vlan_max = kernel_vlan.get_vlan_tag_range()
            if vlan_min == 1 and vlan_max == 1:
                continue
            if is_access_port:
                obj._tag = vlan_min
            elif kernel_vlan.is_pvid and kernel_vlan.is_egress_untagged:
                obj._tag = vlan_max
                obj._is_native = True
            else:
                trunk_tags.append(kernel_vlan.to_dict())

        obj._trunk_tags = trunk_tags
        obj._mode = (
            LB.Port.Vlan.Mode.TRUNK if trunk_tags else LB.Port.Vlan.Mode.ACCESS
        )
        return obj

    def to_kernel_vlans(self):
        kernel_vlans = []
        if self._mode == LB.Port.Vlan.Mode.TRUNK:
            kernel_vlans.extend(
                [
                    NmstateLinuxBridgePortVlan._trunk_tag_to_kernel_vlan(
                        trunk_tag
                    )
                    for trunk_tag in self._trunk_tags
                ]
            )
            if self._is_native and self._tag:
                kernel_vlans.append(
                    KernelBridgePortVlans(
                        vid_min=self._tag,
                        vid_max=self._tag,
                        is_pvid=True,
                        is_egress_untagged=True,
                    )
                )
        elif self._mode == LB.Port.Vlan.Mode.ACCESS and self._tag:
            kernel_vlans.append(
                KernelBridgePortVlans(
                    vid_min=self._tag,
                    vid_max=self._tag,
                    is_pvid=True,
                    is_egress_untagged=True,
                )
            )
        return kernel_vlans

    @staticmethod
    def _trunk_tag_to_kernel_vlan(trunk_tag):
        vid_min = vid_max = trunk_tag.get(LB.Port.Vlan.TrunkTags.ID)
        if vid_min is None:
            ranged_vlan_tags = trunk_tag.get(LB.Port.Vlan.TrunkTags.ID_RANGE)
            vid_min = ranged_vlan_tags[LB.Port.Vlan.TrunkTags.MIN_RANGE]
            vid_max = ranged_vlan_tags[LB.Port.Vlan.TrunkTags.MAX_RANGE]

        return KernelBridgePortVlans(
            vid_min=vid_min,
            vid_max=vid_max,
            is_pvid=False,
            is_egress_untagged=False,
        )

    def to_dict(self, expand_vlan_range=False):
        trunk_tags = self._trunk_tags if self._trunk_tags else []

        if expand_vlan_range and trunk_tags:
            trunk_tags = _expand_trunk_tags(self._trunk_tags)

        port_vlan_info = {
            LB.Port.Vlan.MODE: self._mode,
            LB.Port.Vlan.TRUNK_TAGS: trunk_tags,
        }
        if self._tag:
            port_vlan_info[LB.Port.Vlan.TAG] = self._tag
        if self._mode == LB.Port.Vlan.Mode.TRUNK:
            port_vlan_info[LB.Port.Vlan.ENABLE_NATIVE] = self._is_native
        return port_vlan_info

    @staticmethod
    def _is_access_port(kernel_vlans):
        return (
            len(kernel_vlans) == 1
            and kernel_vlans[0].is_pvid
            and kernel_vlans[0].is_egress_untagged
        )


def _expand_trunk_tags(trunk_tags):
    expanded_trunk_tags = []
    for trunk_tag in trunk_tags:
        if LB.Port.Vlan.TrunkTags.ID_RANGE in trunk_tag:
            vid_range = trunk_tag[LB.Port.Vlan.TrunkTags.ID_RANGE]
            vid_min = vid_range[LB.Port.Vlan.TrunkTags.MIN_RANGE]
            vid_max = vid_range[LB.Port.Vlan.TrunkTags.MAX_RANGE]
            for vid in range(vid_min, vid_max + 1):
                expanded_trunk_tags.append({LB.Port.Vlan.TrunkTags.ID: vid})
        elif LB.Port.Vlan.TrunkTags.ID in trunk_tag:
            expanded_trunk_tags.append(
                {
                    LB.Port.Vlan.TrunkTags.ID: trunk_tag[
                        LB.Port.Vlan.TrunkTags.ID
                    ]
                }
            )
    expanded_trunk_tags.sort(key=itemgetter(LB.Port.Vlan.TrunkTags.ID))
    return expanded_trunk_tags
