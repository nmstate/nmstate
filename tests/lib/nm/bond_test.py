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


@pytest.fixture()
def dev_mock():
    return mock.MagicMock()


@mock.patch.object(nm.bond, "NM")
def test_create_setting(NM_mock):
    bond_setting_mock = NM_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = True

    options = {"mode": "balance-rr", "miimon": "100"}
    nm.bond.create_setting(options)

    bond_setting_mock.add_option.assert_has_calls(
        [mock.call("mode", "balance-rr"), mock.call("miimon", "100")],
        any_order=True,
    )


@mock.patch.object(nm.bond, "NM")
def test_create_setting_with_invalid_bond_option(NM_mock):
    bond_setting_mock = NM_mock.SettingBond.new.return_value
    bond_setting_mock.add_option.return_value = False

    options = {"mode": "balance-rr", "foo": "100"}

    with pytest.raises(NmstateValueError):
        nm.bond.create_setting(options)


@mock.patch.object(nm.bond, "NM")
def test_is_bond_type_id(NM_mock):
    type_id = NM_mock.DeviceType.BOND

    assert nm.bond.is_bond_type_id(type_id)


@mock.patch.object(nm.bond.connection, "ConnectionProfile")
def test_get_bond_info(con_profile_mock, dev_mock):
    ctx = mock.MagicMock()
    info = nm.bond.get_bond_info(ctx, dev_mock)

    con_profile_mock.return_value.import_by_device.assert_called_once_with(
        dev_mock
    )

    connection_mock = con_profile_mock.return_value.profile
    opts_mock = connection_mock.get_setting_bond.return_value.props.options

    expected_info = {
        "slaves": dev_mock.get_slaves.return_value,
        "options": opts_mock,
    }
    assert expected_info == info
