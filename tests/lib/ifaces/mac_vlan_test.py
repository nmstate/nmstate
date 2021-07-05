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
from libnmstate.schema import MacVlan
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.macvlan import MacVlanIface

from ..testlib.ifacelib import gen_foo_iface_info


BASE_IFACE_NAME = "base1"


class TestMacVlanIface:
    def _gen_base_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.ETHERNET)
        iface_info[Interface.NAME] = BASE_IFACE_NAME
        iface_info[Interface.MTU] = 1500

        return iface_info

    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.MAC_VLAN)
        iface_info[MacVlan.CONFIG_SUBTREE] = {
            MacVlan.BASE_IFACE: BASE_IFACE_NAME,
            MacVlan.MODE: MacVlan.Mode.PASSTHRU,
            MacVlan.PROMISCUOUS: True,
        }
        return iface_info

    def test_get_parent(self):
        assert MacVlanIface(self._gen_iface_info()).parent == BASE_IFACE_NAME

    def test_need_parent(self):
        assert MacVlanIface(self._gen_iface_info()).need_parent

    def test_is_virtual(self):
        assert MacVlanIface(self._gen_iface_info()).is_virtual

    def test_can_have_ip_when_enslaved(self):
        assert not MacVlanIface(
            self._gen_iface_info()
        ).can_have_ip_when_enslaved

    def test_get_mode(self):
        assert (
            MacVlanIface(self._gen_iface_info()).mode == MacVlan.Mode.PASSTHRU
        )

    def test_get_base_iface(self):
        assert (
            MacVlanIface(self._gen_iface_info()).base_iface == BASE_IFACE_NAME
        )

    def test_get_promiscuous(self):
        assert MacVlanIface(self._gen_iface_info()).promiscuous

    def test_add_macvlan_without_mode(self):
        iface_info = self._gen_iface_info()
        iface_info[MacVlan.CONFIG_SUBTREE].pop(MacVlan.MODE)

        iface = MacVlanIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_add_macvlan_without_base_iface(self):
        iface_info = self._gen_iface_info()
        iface_info[MacVlan.CONFIG_SUBTREE].pop(MacVlan.BASE_IFACE)

        iface = MacVlanIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_add_macvlan_not_passthru_and_not_promisc(self):
        iface_info = self._gen_iface_info()
        iface_info[MacVlan.CONFIG_SUBTREE][MacVlan.MODE] = MacVlan.Mode.VEPA
        iface_info[MacVlan.CONFIG_SUBTREE][MacVlan.PROMISCUOUS] = False

        iface = MacVlanIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    @pytest.mark.parametrize(
        "mode",
        [
            MacVlan.Mode.VEPA,
            MacVlan.Mode.BRIDGE,
            MacVlan.Mode.PRIVATE,
            MacVlan.Mode.PASSTHRU,
            MacVlan.Mode.SOURCE,
        ],
    )
    def test_valid_mac_vlan_modes(self, mode):
        iface_info = self._gen_iface_info()
        iface_info[MacVlan.CONFIG_SUBTREE] = {
            MacVlan.BASE_IFACE: "eth1",
            MacVlan.MODE: mode,
            MacVlan.PROMISCUOUS: True,
        }
        iface = MacVlanIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    def test_invalid_mac_vlan_mode(self):
        iface_info = self._gen_iface_info()
        iface_info[MacVlan.CONFIG_SUBTREE] = {
            MacVlan.BASE_IFACE: "eth1",
            MacVlan.MODE: "wrongmode",
            MacVlan.PROMISCUOUS: True,
        }
        iface = MacVlanIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()
