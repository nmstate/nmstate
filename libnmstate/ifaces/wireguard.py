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

from libnmstate.schema import Wireguard

from .base_iface import BaseIface


class WireguardIface(BaseIface):
    @property
    def is_virtual(self):
        return True

    @property
    def config_subtree(self):
        return self.raw.get(Wireguard.CONFIG_SUBTREE, {})

    @property
    def fwmark(self):
        return self.config_subtree.get(Wireguard.FWMARK)

    @property
    def listen_port(self):
        return self.config_subtree.get(Wireguard.LISTEN_PORT)

    @property
    def private_key(self):
        return self.config_subtree.get(Wireguard.PRIVATE_KEY)

    @property
    def peers(self):
        return self.config_subtree.get(Wireguard.Peer.CONFIG_SUBTREE, [])
