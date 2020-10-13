#
# Copyright (c) 2018-2019 Red Hat, Inc.
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
from unittest import mock

from libnmstate import nm
from libnmstate.error import NmstateValueError
from libnmstate.ifaces.bond import BondIface
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType


@pytest.fixture
def nm_mock():
    with mock.patch.object(nm.bond, "NM") as m:
        yield m


def _gen_bond_iface(bond_options, mode=BondMode.ROUND_ROBIN):
    return BondIface(
        {
            Interface.NAME: "foo",
            Interface.TYPE: InterfaceType.BOND,
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: mode,
                Bond.OPTIONS_SUBTREE: bond_options,
            },
        }
    )


def test_create_setting(nm_mock):
    bond_setting_mock = nm_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = True

    iface = _gen_bond_iface({"miimon": "100"})
    nm.bond.create_setting(iface, wired_setting=None, base_con_profile=None)

    bond_setting_mock.add_option.assert_has_calls(
        [
            mock.call(Bond.MODE, BondMode.ROUND_ROBIN),
            mock.call("miimon", "100"),
        ],
        any_order=True,
    )


def test_create_setting_with_invalid_bond_option(nm_mock):
    bond_setting_mock = nm_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = False

    iface = _gen_bond_iface({"foo": "100"})

    with pytest.raises(NmstateValueError):
        nm.bond.create_setting(
            iface, wired_setting=None, base_con_profile=None
        )


def test_create_setting_with_mac_restriction(nm_mock):
    bond_setting_mock = nm_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = True

    iface = _gen_bond_iface(
        {"fail_over_mac": "active"}, BondMode.ACTIVE_BACKUP
    )

    wired_setting = mock.MagicMock()
    wired_setting.props.cloned_mac_address = "02:ff:ff:ff:ff:01"

    nm.bond.create_setting(iface, wired_setting, base_con_profile=None)
    assert wired_setting.props.cloned_mac_address is None
