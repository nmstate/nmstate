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

from libnmstate.ifaces.veth import VethIface

from ..testlib.ifacelib import gen_foo_iface_info


VETHTEST_PEER_IFACE = "vethtestpeer"


class TestVethIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.VETH)
        iface_info[Veth.CONFIG_SUBTREE] = {
            Veth.PEER: VETHTEST_PEER_IFACE,
        }
        return iface_info

    def test_veth_is_virtual(self):
        assert VethIface(self._gen_iface_info()).is_virtual

    def test_veth_peer(self):
        assert VethIface(self._gen_iface_info()).peer == VETHTEST_PEER_IFACE
