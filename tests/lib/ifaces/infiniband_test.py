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
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.ifaces import Ifaces
from libnmstate.schema import InfiniBand
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge
from libnmstate.schema import OVSBridge

from libnmstate.ifaces.infiniband import InfiniBandIface

from ..testlib.ifacelib import gen_foo_iface_info
from ..testlib.bridgelib import gen_bridge_iface_info
from ..testlib.ovslib import gen_ovs_bridge_info

BASE_IFACE_NAME = "ib0"
TEST_PKEY = "0x8001"
PKEY_IFACE_NAME = f"{BASE_IFACE_NAME}.{TEST_PKEY[2:]}"


class TestInfiniBandIface:
    def _gen_base_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.INFINIBAND)
        iface_info[Interface.NAME] = BASE_IFACE_NAME
        iface_info[Interface.MTU] = 1500
        iface_info[InfiniBand.CONFIG_SUBTREE] = {
            InfiniBand.PKEY: InfiniBand.DEFAULT_PKEY,
            InfiniBand.MODE: InfiniBand.Mode.DATAGRAM,
        }

        return iface_info

    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.INFINIBAND)
        iface_info[Interface.NAME] = PKEY_IFACE_NAME
        iface_info[InfiniBand.CONFIG_SUBTREE] = {
            InfiniBand.PKEY: TEST_PKEY,
            InfiniBand.MODE: InfiniBand.Mode.DATAGRAM,
            InfiniBand.BASE_IFACE: BASE_IFACE_NAME,
        }
        return iface_info

    def test_get_parent(self):
        assert (
            InfiniBandIface(self._gen_iface_info()).parent == BASE_IFACE_NAME
        )

    def test_need_parent(self):
        assert InfiniBandIface(self._gen_iface_info()).need_parent

    def test_base_iface_not_need_parent(self):
        assert not InfiniBandIface(self._gen_base_iface_info()).need_parent

    def test_is_not_virtual(self):
        assert not InfiniBandIface(self._gen_iface_info()).is_virtual

    def test_cannot_have_ip_as_port(self):
        assert not InfiniBandIface(self._gen_iface_info()).can_have_ip_as_port

    def test_validate_base_iface_missing(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE].pop(InfiniBand.BASE_IFACE)

        iface = InfiniBandIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_mode_missing(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE].pop(InfiniBand.MODE)

        iface = InfiniBandIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_cannonicalize_undefined_pkey(self):
        iface_info = self._gen_base_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE].pop(InfiniBand.PKEY)

        iface = InfiniBandIface(iface_info)
        iface.pre_edit_validation_and_cleanup()
        assert (
            iface.to_dict()[InfiniBand.CONFIG_SUBTREE][InfiniBand.PKEY]
            == InfiniBand.DEFAULT_PKEY
        )

    def test_cannonicalize_hex_string_pkey_to_numer(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE][InfiniBand.PKEY] = TEST_PKEY

        iface = InfiniBandIface(iface_info)
        iface.pre_edit_validation_and_cleanup()
        assert iface.to_dict()[InfiniBand.CONFIG_SUBTREE][
            InfiniBand.PKEY
        ] == int(TEST_PKEY, 16)

    def test_cannonicalize_string_pkey_to_numer(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE][
            InfiniBand.PKEY
        ] = f"{int(TEST_PKEY, 16)}"

        iface = InfiniBandIface(iface_info)
        iface.pre_edit_validation_and_cleanup()
        assert iface.to_dict()[InfiniBand.CONFIG_SUBTREE][
            InfiniBand.PKEY
        ] == int(TEST_PKEY, 16)

    def test_cannonicalize_invalid_string_pkey(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE][InfiniBand.PKEY] = "invalid_pkey"

        iface = InfiniBandIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_cannonicalize_pkey_bigger_than_maximum(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE][InfiniBand.PKEY] = 0xFFFF + 1

        iface = InfiniBandIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_cannonicalize_pkey_smaller_than_minimum(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE][InfiniBand.PKEY] = 0

        iface = InfiniBandIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_invalid_iface_name(self):
        iface_info = self._gen_iface_info()
        iface_info[Interface.NAME] = "invalid_pkey"

        iface = InfiniBandIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_verify_string_pkey(self):
        iface_info = self._gen_iface_info()
        iface_info[InfiniBand.CONFIG_SUBTREE][InfiniBand.PKEY] = int(
            TEST_PKEY, 16
        )

        iface = InfiniBandIface(iface_info)
        current_iface = InfiniBandIface(self._gen_iface_info())
        iface.match(current_iface)

    def test_remove_base_iface_got_child_marked_as_absent(self):
        base_iface_info = self._gen_base_iface_info()
        base_iface_info[Interface.STATE] = InterfaceState.ABSENT
        ifaces = Ifaces([base_iface_info, self._gen_iface_info()], [])
        ifaces[PKEY_IFACE_NAME].state = InterfaceState.ABSENT
        ifaces[BASE_IFACE_NAME].state = InterfaceState.ABSENT

    def test_expect_exception_for_adding_ib_to_linux_bridge(self):
        base_iface_info = self._gen_base_iface_info()
        ib_iface_info = self._gen_iface_info()
        bridge_iface_info = gen_bridge_iface_info()
        bridge_config = bridge_iface_info[LinuxBridge.CONFIG_SUBTREE]
        bridge_config[LinuxBridge.PORT_SUBTREE] = [
            {LinuxBridge.Port.NAME: PKEY_IFACE_NAME}
        ]
        with pytest.raises(NmstateValueError):
            Ifaces([base_iface_info, ib_iface_info, bridge_iface_info], [])

    def test_expect_exception_for_adding_ib_to_ovs_bridge(self):
        base_iface_info = self._gen_base_iface_info()
        ib_iface_info = self._gen_iface_info()
        bridge_iface_info = gen_ovs_bridge_info()
        bridge_config = bridge_iface_info[OVSBridge.CONFIG_SUBTREE]
        bridge_config[OVSBridge.PORT_SUBTREE] = [
            {OVSBridge.Port.NAME: PKEY_IFACE_NAME}
        ]
        with pytest.raises(NmstateValueError):
            Ifaces([base_iface_info, ib_iface_info, bridge_iface_info], [])

    def test_add_ib_to_bond_not_in_active_backup_mode(self):
        base_iface_info = self._gen_base_iface_info()
        ib_iface_info = self._gen_iface_info()
        bond_iface_info = gen_foo_iface_info(iface_type=InterfaceType.BOND)
        bond_iface_info[Bond.CONFIG_SUBTREE] = {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.PORT: [PKEY_IFACE_NAME],
            Bond.OPTIONS_SUBTREE: {},
        }

        with pytest.raises(NmstateValueError):
            Ifaces([base_iface_info, ib_iface_info, bond_iface_info], [])

    def test_add_ib_to_bond_in_active_backup_mode(self):
        base_iface_info = self._gen_base_iface_info()
        ib_iface_info = self._gen_iface_info()
        bond_iface_info = gen_foo_iface_info(iface_type=InterfaceType.BOND)
        bond_iface_info[Bond.CONFIG_SUBTREE] = {
            Bond.MODE: BondMode.ACTIVE_BACKUP,
            Bond.PORT: [PKEY_IFACE_NAME],
            Bond.OPTIONS_SUBTREE: {},
        }

        Ifaces([base_iface_info, ib_iface_info, bond_iface_info], [])
