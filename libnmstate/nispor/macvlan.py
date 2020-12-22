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

from libnmstate.schema import InterfaceType
from libnmstate.schema import MacVlan

from .base_iface import NisporPluginBaseIface


MACVLAN_FLAG_NOPROMISC = 1


MACVLAN_MODES = {
    "unknown": MacVlan.Mode.UNKNOWN,
    "vepa": MacVlan.Mode.VEPA,
    "bridge": MacVlan.Mode.BRIDGE,
    "private": MacVlan.Mode.PRIVATE,
    "passthru": MacVlan.Mode.PASSTHRU,
    "source": MacVlan.Mode.SOURCE,
}


class NisporPluginMacVlanIface(NisporPluginBaseIface):
    @property
    def type(self):
        return InterfaceType.MAC_VLAN

    def to_dict(self, config_only):
        info = super().to_dict(config_only)
        info[MacVlan.CONFIG_SUBTREE] = {
            MacVlan.BASE_IFACE: self._np_iface.base_iface,
            MacVlan.MODE: MACVLAN_MODES.get(
                self._np_iface.mode, MacVlan.Mode.UNKNOWN
            ),
            MacVlan.PROMISCUOUS: self._flag_to_promiscuous(
                self._np_iface.mac_vlan_flags
            ),
        }

        return info

    @staticmethod
    def _flag_to_promiscuous(flags):
        return (flags & MACVLAN_FLAG_NOPROMISC) == 0
