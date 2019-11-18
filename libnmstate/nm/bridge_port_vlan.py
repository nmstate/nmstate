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


from libnmstate.nm import nmclient
from libnmstate.schema import LinuxBridge as LB


class PortVlanFilter(object):
    Pvid = "pvid"
    Untagged = "untagged"

    def __init__(self):
        self._trunk_ports = []
        self._tag = None
        self._is_native_vlan = None
        self._port_type = None

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
        self._trunk_ports = trunk_tags
        self._tag = tag
        self._is_native_vlan = is_native_vlan
        self._port_type = (
            LB.Port.Vlan.Mode.TRUNK if trunk_tags else LB.Port.Vlan.Mode.ACCESS
        )

    @property
    def trunk_ports(self):
        return self._trunk_ports

    @property
    def tag(self):
        return self._tag

    @property
    def enable_native_vlan(self):
        return self._is_native_vlan

    @property
    def port_type(self):
        return self._port_type

    def to_nm(self):
        """
        Generate a list of NM.BridgeVlan objects from the encapsulated
        PortVlanFilter data
        """

        port_vlan_config = []
        if self.port_type == LB.Port.Vlan.Mode.TRUNK:
            for trunk_port in self.trunk_ports:
                port_vlan_config.append(
                    self._generate_vlan_trunk_port_config(trunk_port)
                )
            if self.enable_native_vlan and self.tag:
                port_vlan_config.append(
                    self._generate_vlan_access_port_config(self.tag)
                )
        elif self.port_type == LB.Port.Vlan.Mode.ACCESS and self.tag:
            port_vlan_config.append(
                self._generate_vlan_access_port_config(self.tag)
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
            LB.Port.Vlan.MODE: self.port_type,
            LB.Port.Vlan.TRUNK_TAGS: self.trunk_ports,
        }
        if self.tag:
            port_vlan_state[LB.Port.Vlan.TAG] = self.tag
        if self.port_type == LB.Port.Vlan.Mode.TRUNK:
            port_vlan_state[
                LB.Port.Vlan.ENABLE_NATIVE
            ] = self.enable_native_vlan
        return port_vlan_state

    def import_from_bridge_settings(self, port_vlans):
        """
        Instantiates a PortVlanFilter object from a list of NM.BridgeVlan
        objects.
        """

        bridge_vlan_config = [
            self._get_vlan_info(port_vlan_filter_entry)
            for port_vlan_filter_entry in port_vlans
        ]

        trunk_tags, tag, enable_native = self._get_vlan_config(
            bridge_vlan_config
        )

        self._trunk_ports = trunk_tags
        self._tag = tag
        self._is_native_vlan = enable_native
        self._port_type = (
            LB.Port.Vlan.Mode.TRUNK if trunk_tags else LB.Port.Vlan.Mode.ACCESS
        )

    @staticmethod
    def get_vlan_tag_range(port_vlan):
        """
        Extract the vlan tags from the NM.BridgeVlan object.
        A single NM.BridgeVlan object can have a range of vlan tags, or a
        single one.

        When a NM.BridgeVlan holds a single tag, the min_range, and max_range
        returned will have the same vlan tag.

        :return: min_range, max_range
        """

        port_vlan_tags = port_vlan.to_str().split()

        if "-" in port_vlan_tags[0]:
            vlan_min, vlan_max = port_vlan_tags[0].split("-")
            return int(vlan_min), int(vlan_max)
        else:
            tag = port_vlan_tags[0]
            return int(tag), int(tag)

    @staticmethod
    def _is_access_port(trunk_tags):
        if (
            len(trunk_tags) == 1
            and trunk_tags[0][PortVlanFilter.Pvid]
            and trunk_tags[0][PortVlanFilter.Untagged]
        ):
            return True
        else:
            return False

    @staticmethod
    def _get_vlan_info(port_vlan_info):
        vlan_min, vlan_max = PortVlanFilter.get_vlan_tag_range(port_vlan_info)
        pvid = port_vlan_info.is_pvid()
        untagged = port_vlan_info.is_untagged()
        if vlan_max != vlan_min:
            port_data = {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: vlan_min,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: vlan_max,
                }
            }
        else:
            port_data = {LB.Port.Vlan.TrunkTags.ID: vlan_min}
        port_data.update(pvid=pvid, untagged=untagged)
        return port_data

    @staticmethod
    def _generate_vlan_trunk_port_config(trunk_port):
        single_vlan_tag = trunk_port.get(LB.Port.Vlan.TrunkTags.ID)
        ranged_vlan_tags = trunk_port.get(LB.Port.Vlan.TrunkTags.ID_RANGE)
        port_vlan = None

        if single_vlan_tag:
            port_vlan = nmclient.NM.BridgeVlan.new(
                single_vlan_tag, single_vlan_tag
            )
        elif ranged_vlan_tags:
            min_range, max_range = (
                ranged_vlan_tags[range_type]
                for range_type in (
                    LB.Port.Vlan.TrunkTags.MIN_RANGE,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE,
                )
            )
            port_vlan = nmclient.NM.BridgeVlan.new(min_range, max_range)
        port_vlan.set_untagged(False)
        port_vlan.set_pvid(False)
        return port_vlan

    @staticmethod
    def _generate_vlan_access_port_config(vlan_tag):
        port_vlan = nmclient.NM.BridgeVlan.new(vlan_tag, vlan_tag)
        port_vlan.set_untagged(True)
        port_vlan.set_pvid(True)
        return port_vlan

    @staticmethod
    def _get_vlan_config(bridge_vlan_config):
        enable_native = False
        trunk_tags = []
        tag = None

        for port_vlan_filter_entry in bridge_vlan_config:
            single_vlan_tag = port_vlan_filter_entry.get(
                LB.Port.Vlan.TrunkTags.ID
            )
            ranged_vlan_tags = port_vlan_filter_entry.get(
                LB.Port.Vlan.TrunkTags.ID_RANGE
            )
            if PortVlanFilter._is_access_port(bridge_vlan_config):
                tag = single_vlan_tag
            else:
                if port_vlan_filter_entry[PortVlanFilter.Pvid]:
                    tag = (
                        single_vlan_tag
                        or ranged_vlan_tags[LB.Port.Vlan.TrunkTags.MAX_RANGE]
                    )
                    enable_native = True
                else:
                    PortVlanFilter._sanitize_trunk_port(port_vlan_filter_entry)
                    trunk_tags.append(port_vlan_filter_entry)

        return trunk_tags, tag, enable_native

    @staticmethod
    def _sanitize_trunk_port(port):
        if PortVlanFilter.Pvid and PortVlanFilter.Untagged in port:
            del port[PortVlanFilter.Pvid]
            del port[PortVlanFilter.Untagged]
