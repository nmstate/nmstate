#
# Copyright (c) 2021 Red Hat, Inc.
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
from libnmstate.schema import Veth
from libnmstate.validator import validate_string

from .ethernet import EthernetIface


class VethIface(EthernetIface):
    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._peer_changed = False

    @property
    def is_virtual(self):
        return True

    @property
    def peer(self):
        return self.raw.get(Veth.CONFIG_SUBTREE, {}).get(Veth.PEER)

    @property
    def is_peer_changed(self):
        return self._peer_changed

    def mark_as_peer(self):
        self._is_peer = True

    def _mark_iface_is_peer(self, ifaces):
        if (
            not self.is_absent
            and not ifaces.get_cur_iface(self.peer, self.type)
            and not ifaces.get_cur_iface(self.name, self.type)
        ):
            for iface in ifaces.all_ifaces():
                if iface.name == self.peer and (
                    self.type == iface.type
                    or iface.type == InterfaceType.ETHERNET
                ):
                    if not self.is_peer:
                        iface._is_peer = True

    def _mark_peer_changed(self, ifaces):
        if self.is_up:
            cur_iface = ifaces.get_cur_iface(self.name, self.type)
            if cur_iface and self.peer != cur_iface.peer:
                self._peer_changed = True

    def gen_metadata(self, ifaces):
        self._mark_iface_is_peer(ifaces)
        self._mark_peer_changed(ifaces)
        super().gen_metadata(ifaces)

    def pre_edit_validation_and_cleanup(self):
        validate_string(self.peer, Veth.PEER)
        super().pre_edit_validation_and_cleanup()
