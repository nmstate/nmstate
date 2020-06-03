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

from copy import deepcopy

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.ifaces import Ifaces
from libnmstate.ifaces.bond import BondIface

from ..testlib.constants import FOO_IFACE_NAME
from ..testlib.constants import MAC_ADDRESS1
from ..testlib.ifacelib import gen_foo_iface_info

SLAVE1_IFACE_NAME = "slave1"
SLAVE2_IFACE_NAME = "slave2"


TEST_SLAVES = [SLAVE1_IFACE_NAME, SLAVE2_IFACE_NAME]
TEST_BOND_MODE = BondMode.ROUND_ROBIN

parametrize_bond_named_options = pytest.mark.parametrize(
    ("option_name", "name_value", "int_value"),
    (
        ("ad_select", "stable", 0),
        ("ad_select", "bandwidth", 1),
        ("ad_select", "count", 2),
        ("arp_validate", "active", 1),
        ("arp_validate", "filter", 4),
        ("arp_validate", "filter_backup", 6),
        ("fail_over_mac", "none", 0),
        ("fail_over_mac", "active", 1),
        ("fail_over_mac", "follow", 2),
    ),
)


class TestBondIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.BOND)
        iface_info[Bond.CONFIG_SUBTREE] = {
            Bond.MODE: TEST_BOND_MODE,
            Bond.SLAVES: deepcopy(TEST_SLAVES),
            Bond.OPTIONS_SUBTREE: {},
        }
        return iface_info

    def _gen_slave1_iface_info(self):
        iface_info = gen_foo_iface_info()
        iface_info[Interface.NAME] = SLAVE1_IFACE_NAME
        return iface_info

    def _gen_slave2_iface_info(self):
        iface_info = gen_foo_iface_info()
        iface_info[Interface.NAME] = SLAVE2_IFACE_NAME
        return iface_info

    def _gen_ifaces(self, bond_iface_info):
        return Ifaces(
            des_iface_infos=[
                bond_iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
            cur_iface_infos=[],
        )

    def test_bond_sort_slaves(self):
        iface_info1 = self._gen_iface_info()
        iface_info2 = self._gen_iface_info()
        iface_info2[Bond.CONFIG_SUBTREE][Bond.SLAVES].reverse()

        assert iface_info2 != iface_info1
        assert (
            BondIface(iface_info1).state_for_verify()
            == BondIface(iface_info2).state_for_verify()
        )

    def test_normalize_bond_option_str_to_integer(self):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "miimon": "140"
        }
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "miimon": 140
        }

        assert BondIface(iface_info).to_dict() == expected_iface_info

    @parametrize_bond_named_options
    def test_normalize_bond_option_int_to_named(
        self, option_name, name_value, int_value
    ):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            option_name: int_value,
        }
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            option_name: name_value
        }

        assert BondIface(iface_info).to_dict() == expected_iface_info

    @parametrize_bond_named_options
    def test_normalize_bond_option_int_str_to_named(
        self, option_name, name_value, int_value
    ):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            option_name: f"{int_value}",
        }
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            option_name: name_value
        }

        assert BondIface(iface_info).to_dict() == expected_iface_info

    def test_normalize_bond_named_option_invalid_choice_preserved_as_int(self):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "ad_select": "99",
        }
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "ad_select": 99
        }

        assert BondIface(iface_info).to_dict() == expected_iface_info

    def test_include_arp_ip_target_explictly_when_disable(self):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "arp_interval": 0,
        }
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "arp_interval": 0,
            "arp_ip_target": "",
        }

        assert BondIface(iface_info).to_dict() == expected_iface_info

    def test_include_arp_ip_target_explictly_when_disable_in_verify(self):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "arp_interval": 0,
        }
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "arp_interval": 0,
            "arp_ip_target": "",
        }

        assert BondIface(iface_info).state_for_verify() == expected_iface_info

    def test_get_slaves(self):
        assert BondIface(self._gen_iface_info()).slaves == TEST_SLAVES

    def test_is_master(self):
        assert BondIface(self._gen_iface_info()).is_master

    def test_is_virtual(self):
        assert BondIface(self._gen_iface_info()).is_virtual

    def test_get_bond_mode(self):
        assert BondIface(self._gen_iface_info()).bond_mode == TEST_BOND_MODE

    def test_get_is_bond_mode_changed(self):
        cur_iface_info = self._gen_iface_info()
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP

        ifaces = Ifaces(
            des_iface_infos=[
                iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
            cur_iface_infos=[
                cur_iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
        )
        bond_iface = ifaces[FOO_IFACE_NAME]
        bond_iface.gen_metadata(ifaces)
        slave1_iface = ifaces[SLAVE1_IFACE_NAME]
        slave2_iface = ifaces[SLAVE2_IFACE_NAME]

        assert slave1_iface.master == FOO_IFACE_NAME
        assert slave2_iface.master == FOO_IFACE_NAME
        assert bond_iface.is_bond_mode_changed

    def test_pre_edit_clean_up_discard_bond_options_when_mode_chagned(self):
        cur_iface_info = self._gen_iface_info()
        cur_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "miimon": 140
        }
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "arp_interval": 140
        }
        expected_iface_info = deepcopy(iface_info)

        ifaces = Ifaces(
            des_iface_infos=[
                iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
            cur_iface_infos=[
                cur_iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
        )
        bond_iface = ifaces[FOO_IFACE_NAME]
        bond_iface.gen_metadata(ifaces)
        bond_iface.pre_edit_validation_and_cleanup()

        assert expected_iface_info == _remove_metadata(bond_iface.to_dict())

    def test_is_mac_restricted_mode(self):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "fail_over_mac": "active"
        }
        assert BondIface(iface_info).is_mac_restricted_mode

    def test_pre_edit_clean_up_discard_mac_address_when_mac_restricted(self):
        cur_iface_info = self._gen_iface_info()
        cur_iface_info[Interface.MAC] = MAC_ADDRESS1
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "fail_over_mac": "active"
        }
        expected_iface_info = deepcopy(iface_info)

        ifaces = Ifaces(
            des_iface_infos=[
                iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
            cur_iface_infos=[
                cur_iface_info,
                self._gen_slave1_iface_info(),
                self._gen_slave2_iface_info(),
            ],
        )
        bond_iface = ifaces[FOO_IFACE_NAME]
        bond_iface.gen_metadata(ifaces)
        bond_iface.pre_edit_validation_and_cleanup()

        assert expected_iface_info == _remove_metadata(bond_iface.to_dict())

    def test_validate_bond_mode_undefined(self):
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE].pop(Bond.MODE)

        with pytest.raises(NmstateValueError):
            BondIface(iface_info).pre_edit_validation_and_cleanup()

    def test_validate_mac_restriced_mode_with_desire_has_no_mac(self):
        cur_iface_info = self._gen_iface_info()
        cur_iface_info[Interface.MAC] = MAC_ADDRESS1
        cur_iface = BondIface(cur_iface_info)
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "fail_over_mac": "active"
        }
        iface = BondIface(iface_info)

        iface.merge(cur_iface)
        iface.pre_edit_validation_and_cleanup()

    def test_validate_mac_restriced_mode_with_desire_has_mac(self):
        cur_iface_info = self._gen_iface_info()
        cur_iface_info[Interface.MAC] = MAC_ADDRESS1
        cur_iface = BondIface(cur_iface_info)
        iface_info = self._gen_iface_info()
        iface_info[Interface.MAC] = MAC_ADDRESS1
        iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
        iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "fail_over_mac": "active"
        }
        iface = BondIface(iface_info)

        iface.merge(cur_iface)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_mac_restriced_mode_with_desire_has_mac_only(self):
        cur_iface_info = self._gen_iface_info()
        cur_iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
        cur_iface_info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
            "fail_over_mac": "active"
        }
        cur_iface = BondIface(cur_iface_info)
        iface_info = self._gen_iface_info()
        iface_info[Bond.CONFIG_SUBTREE].pop(Bond.MODE)
        iface_info[Bond.CONFIG_SUBTREE].pop(Bond.OPTIONS_SUBTREE)
        iface_info[Interface.MAC] = MAC_ADDRESS1
        iface = BondIface(iface_info)

        iface.merge(cur_iface)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_remove_slave(self):
        iface = BondIface(self._gen_iface_info())
        expected_iface_info = self._gen_iface_info()
        expected_iface_info[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [
            SLAVE2_IFACE_NAME
        ]

        iface.remove_slave(SLAVE1_IFACE_NAME)

        assert iface.to_dict() == expected_iface_info


def _remove_metadata(bond_iface_info):
    remove_keys = [k for k in bond_iface_info.keys() if k.startswith("_")]
    for key in remove_keys:
        bond_iface_info.pop(key)
    return bond_iface_info
