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

from libnmstate.schema import LinuxBridge as LB

from .common import NM


class PortVlanFilter:
    def __init__(self):
        self._trunk_tags = []
        self._tag = None
        self._is_native = None
        self._port_mode = None

    def create_configuration(self, trunk_tags, tag, is_native_vlan=False):
        """
        Fill the PortVlanFilter object with data whose format is tied to the
        API.
        :param trunk_tags: list of schema.LinuxBridge.Port.Vlan.TrunkTags
               objects.
        :param tag: the access tag for access ports, the native vlan ID for
               trunk ports
        :param is_native_vlan: boolean attribute indicating if the trunk port
               has a native vlan.
        """
        self._trunk_tags = trunk_tags
        self._tag = tag
        self._is_native = is_native_vlan
        self._port_mode = (
            LB.Port.Vlan.Mode.TRUNK if trunk_tags else LB.Port.Vlan.Mode.ACCESS
        )

    @property
    def trunk_tags(self):
        return self._trunk_tags

    @property
    def tag(self):
        return self._tag

    @property
    def is_native(self):
        return self._is_native

    @property
    def port_mode(self):
        return self._port_mode

    def to_nm(self):
        """
        Generate a list of NM.BridgeVlan objects from the encapsulated
        PortVlanFilter data
        """

        port_vlan_config = []
        if self._port_mode == LB.Port.Vlan.Mode.TRUNK:
            port_vlan_config += map(
                PortVlanFilter._generate_vlan_trunk_port_config,
                self._trunk_tags,
            )
            if self._is_native and self._tag:
                port_vlan_config.append(
                    PortVlanFilter._generate_vlan_access_port_config(self._tag)
                )
        elif self._port_mode == LB.Port.Vlan.Mode.ACCESS and self._tag:
            port_vlan_config.append(
                PortVlanFilter._generate_vlan_access_port_config(self._tag)
            )

        return port_vlan_config

    def to_dict(self):
        """
        Get the port vlan filtering configuration in dict format - e.g. in yaml
        format:
        - name: eth1
          vlan:
            type: trunk
            trunk-tags:
              - id: 101
              - id-range:
                  min: 200
                  max: 4095
            tag: 100
            enable-native: true
        """

        port_vlan_state = {
            LB.Port.Vlan.MODE: self._port_mode,
            LB.Port.Vlan.TRUNK_TAGS: self._trunk_tags,
        }
        if self._tag:
            port_vlan_state[LB.Port.Vlan.TAG] = self._tag
        if self._port_mode == LB.Port.Vlan.Mode.TRUNK:
            port_vlan_state[LB.Port.Vlan.ENABLE_NATIVE] = self._is_native
        return port_vlan_state

    def import_from_bridge_settings(self, nm_bridge_vlans):
        """
        Instantiates a PortVlanFilter object from a list of NM.BridgeVlan
        objects.
        """

        self._is_native = False
        trunk_tags = []

        is_access_port = PortVlanFilter._is_access_port(nm_bridge_vlans)
        for nm_bridge_vlan in nm_bridge_vlans:
            vlan_min, vlan_max = PortVlanFilter.get_vlan_tag_range(
                nm_bridge_vlan
            )
            if is_access_port:
                self._tag = vlan_min
            elif nm_bridge_vlan.is_pvid() and nm_bridge_vlan.is_untagged():
                # an NM.BridgeVlan has a range and can be PVID and/or untagged
                # according to NM's model, PVID / untagged apply to the 'max'
                # part of the range
                self._tag = vlan_max
                self._is_native = True
            else:
                trunk_tags.append(
                    PortVlanFilter._translate_nm_bridge_vlan_to_trunk_tags(
                        vlan_min, vlan_max
                    )
                )

        self._trunk_tags = trunk_tags
        self._port_mode = (
            LB.Port.Vlan.Mode.TRUNK if trunk_tags else LB.Port.Vlan.Mode.ACCESS
        )

    @staticmethod
    def get_vlan_tag_range(nm_bridge_vlan):
        """
        Extract the vlan tags from the NM.BridgeVlan object.
        A single NM.BridgeVlan object can have a range of vlan tags, or a
        single one.
        When a NM.BridgeVlan holds a single tag, the min_range and max_range
        returned will have the same vlan tag.
        :return: min_range, max_range
        """

        port_vlan_tags = nm_bridge_vlan.to_str().split()

        if "-" in port_vlan_tags[0]:
            vlan_min, vlan_max = port_vlan_tags[0].split("-")
            return int(vlan_min), int(vlan_max)
        else:
            tag = int(port_vlan_tags[0])
            return tag, tag

    @staticmethod
    def _is_access_port(nm_bridge_vlan_ports):
        return (
            len(nm_bridge_vlan_ports) == 1
            and nm_bridge_vlan_ports[0].is_pvid()
            and nm_bridge_vlan_ports[0].is_untagged()
        )

    @staticmethod
    def _translate_nm_bridge_vlan_to_trunk_tags(min_vlan, max_vlan):
        if max_vlan != min_vlan:
            port_data = {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan,
                }
            }
        else:
            port_data = {LB.Port.Vlan.TrunkTags.ID: min_vlan}

        return port_data

    @staticmethod
    def _generate_vlan_trunk_port_config(trunk_port):
        min_range = max_range = trunk_port.get(LB.Port.Vlan.TrunkTags.ID)
        if min_range is None:
            ranged_vlan_tags = trunk_port.get(LB.Port.Vlan.TrunkTags.ID_RANGE)
            min_range = ranged_vlan_tags[LB.Port.Vlan.TrunkTags.MIN_RANGE]
            max_range = ranged_vlan_tags[LB.Port.Vlan.TrunkTags.MAX_RANGE]
        port_vlan = NM.BridgeVlan.new(min_range, max_range)
        port_vlan.set_untagged(False)
        port_vlan.set_pvid(False)
        return port_vlan

    @staticmethod
    def _generate_vlan_access_port_config(vlan_tag):
        port_vlan = NM.BridgeVlan.new(vlan_tag, vlan_tag)
        port_vlan.set_untagged(True)
        port_vlan.set_pvid(True)
        return port_vlan
