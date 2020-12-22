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
from libnmstate.schema import MacVtap

from .macvlan import NisporPluginMacVlanIface


MACVTAP_MODES = {
    "unknown": MacVtap.Mode.UNKNOWN,
    "vepa": MacVtap.Mode.VEPA,
    "bridge": MacVtap.Mode.BRIDGE,
    "private": MacVtap.Mode.PRIVATE,
    "passthru": MacVtap.Mode.PASSTHRU,
    "source": MacVtap.Mode.SOURCE,
}


class NisporPluginMacVtapIface(NisporPluginMacVlanIface):
    @property
    def type(self):
        return InterfaceType.MAC_VTAP

    def to_dict(self, config_only):
        info = super().to_dict(config_only)
        info[MacVtap.CONFIG_SUBTREE] = {
            MacVtap.BASE_IFACE: self._np_iface.base_iface,
            MacVtap.MODE: MACVTAP_MODES.get(
                self._np_iface.mode, MacVtap.Mode.UNKNOWN
            ),
            MacVtap.PROMISCUOUS: self._flag_to_promiscuous(
                self._np_iface.mac_vlan_flags
            ),
        }

        return info
