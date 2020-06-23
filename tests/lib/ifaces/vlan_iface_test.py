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

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.ifaces import Ifaces
from libnmstate.schema import VLAN
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.vlan import VlanIface

from ..testlib.ifacelib import gen_foo_iface_info

BASE_IFACE_NAME = "base1"


class TestVlanIface:
    def _gen_base_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.ETHERNET)
        iface_info[Interface.NAME] = BASE_IFACE_NAME
        iface_info[Interface.MTU] = 1500

        return iface_info

    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.VLAN)
        iface_info[VLAN.CONFIG_SUBTREE] = {
            VLAN.ID: 101,
            VLAN.BASE_IFACE: BASE_IFACE_NAME,
        }
        return iface_info

    def test_get_parent(self):
        assert VlanIface(self._gen_iface_info()).parent == BASE_IFACE_NAME

    def test_need_parent(self):
        assert VlanIface(self._gen_iface_info()).need_parent

    def test_is_virtual(self):
        assert VlanIface(self._gen_iface_info()).is_virtual

    def test_can_have_ip_when_enslaved(self):
        assert VlanIface(self._gen_iface_info()).can_have_ip_when_enslaved

    def test_validate_base_iface_missing(self):
        iface_info = self._gen_iface_info()
        iface_info[VLAN.CONFIG_SUBTREE].pop(VLAN.BASE_IFACE)

        iface = VlanIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_add_vlan_with_mtu_greater_than_base(self):
        base_iface_info = self._gen_base_iface_info()
        vlan_iface_info = self._gen_iface_info()
        vlan_iface_info[Interface.MTU] = base_iface_info[Interface.MTU] + 1

        with pytest.raises(NmstateValueError):
            Ifaces(
                des_iface_infos=[base_iface_info, vlan_iface_info],
                cur_iface_infos=[],
            )

    def test_add_vlan_with_base_mtu_undefined(self):
        base_iface_info = self._gen_base_iface_info()
        base_iface_info[Interface.MTU] = None
        vlan_iface_info = self._gen_iface_info()
        vlan_iface_info[Interface.MTU] = 1501

        ifaces = Ifaces(
            des_iface_infos=[base_iface_info, vlan_iface_info],
            cur_iface_infos=[],
        )

        base_iface = ifaces.get(base_iface_info.get(Interface.NAME))

        assert base_iface.mtu == vlan_iface_info[Interface.MTU]
