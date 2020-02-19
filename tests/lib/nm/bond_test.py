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
from libnmstate.schema import Bond
from libnmstate.schema import BondMode


@pytest.fixture()
def dev_mock():
    return mock.MagicMock()


@mock.patch.object(nm.bond.nmclient, "NM")
def test_create_setting(NM_mock):
    bond_setting_mock = NM_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = True

    options = {Bond.MODE: BondMode.ROUND_ROBIN, "miimon": "100"}
    nm.bond.create_setting(options)

    bond_setting_mock.add_option.assert_has_calls(
        [
            mock.call(Bond.MODE, BondMode.ROUND_ROBIN),
            mock.call("miimon", "100"),
        ],
        any_order=True,
    )


@mock.patch.object(nm.bond.nmclient, "NM")
def test_create_setting_with_invalid_bond_option(NM_mock):
    bond_setting_mock = NM_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = False

    options = {Bond.MODE: BondMode.ROUND_ROBIN, "foo": "100"}

    with pytest.raises(NmstateValueError):
        nm.bond.create_setting(options)


@mock.patch.object(nm.bond.nmclient, "NM")
def test_is_bond_type_id(NM_mock):
    type_id = NM_mock.DeviceType.BOND

    assert nm.bond.is_bond_type_id(type_id)
