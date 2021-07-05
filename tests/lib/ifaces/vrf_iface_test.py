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
from libnmstate.schema import VRF
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.vrf import VrfIface

from ..testlib.constants import MAC_ADDRESS1
from ..testlib.ifacelib import gen_foo_iface_info

PORT1_IFACE_NAME = "port1"
PORT2_IFACE_NAME = "port2"


class TestVrfIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.VRF)
        iface_info[VRF.CONFIG_SUBTREE] = {
            VRF.PORT_SUBTREE: [PORT1_IFACE_NAME, PORT2_IFACE_NAME],
            VRF.ROUTE_TABLE_ID: 100,
        }
        return iface_info

    def test_vrf_is_virtual(self):
        assert VrfIface(self._gen_iface_info()).is_virtual

    def test_vrf_is_controller(self):
        assert VrfIface(self._gen_iface_info()).is_controller

    def test_vrf_sort_ports(self):
        iface1_info = self._gen_iface_info()
        iface2_info = self._gen_iface_info()
        iface2_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].reverse()

        iface1 = VrfIface(iface1_info)
        iface2 = VrfIface(iface2_info)

        assert iface1.state_for_verify() == iface2.state_for_verify()

    def test_vrf_remove_port(self):
        iface_info = self._gen_iface_info()
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].pop()

        iface = VrfIface(iface_info)
        assert iface.port == [PORT1_IFACE_NAME]

    def test_validate_missing_table_id(self):
        iface_info = self._gen_iface_info()
        iface_info[VRF.CONFIG_SUBTREE].pop(VRF.ROUTE_TABLE_ID)
        iface = VrfIface(iface_info)
        iface.mark_as_desired()
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_remove_mac_address(self):
        iface_info = self._gen_iface_info()
        iface_info[Interface.MAC] = MAC_ADDRESS1
        iface = VrfIface(iface_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()
        assert Interface.MAC not in iface.original_desire_dict
        assert Interface.MAC not in iface.to_dict()

    def test_remove_accept_all_mac_addresses_false(self):
        iface_info = self._gen_iface_info()
        iface_info[Interface.ACCEPT_ALL_MAC_ADDRESSES] = False
        iface = VrfIface(iface_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

        assert (
            Interface.ACCEPT_ALL_MAC_ADDRESSES
            not in iface.original_desire_dict
        )
        assert Interface.ACCEPT_ALL_MAC_ADDRESSES not in iface.to_dict()

    def test_valid_vrf_interface_with_ports(self):
        iface_info = self._gen_iface_info()

        iface = VrfIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    def test_invalid_vrf_ports(self):
        iface_info = self._gen_iface_info()
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = ["foo1", 34, []]

        iface = VrfIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_invalid_vrf_route_table_id(self):
        iface_info = self._gen_iface_info()
        iface_info[VRF.CONFIG_SUBTREE][VRF.ROUTE_TABLE_ID] = "wrongtype"

        iface = VrfIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()
