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

from libnmstate.schema import Veth

from .ethernet import EthernetIface


_IS_PEER_METADATA = "_is_peer"


class VethIface(EthernetIface):
    @property
    def is_virtual(self):
        return True

    @property
    def peer(self):
        return self.raw.get(Veth.CONFIG_SUBTREE, {}).get(Veth.PEER)

    @property
    def is_peer(self):
        return self.raw.get(_IS_PEER_METADATA) is True

    def mark_as_peer(self):
        self.raw[_IS_PEER_METADATA] = True

    def gen_metadata(self, ifaces):
        if (
            not self.is_absent
            and not ifaces.get_cur_iface(self.peer, self.type)
            and not ifaces.get_cur_iface(self.name, self.type)
        ):
            for iface in ifaces.all_ifaces():
                if iface.name == self.peer and iface.type == self.type:
                    if not iface.raw.get(_IS_PEER_METADATA):
                        self.raw[_IS_PEER_METADATA] = True
        super().gen_metadata(ifaces)
