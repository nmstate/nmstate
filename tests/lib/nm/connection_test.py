#
# Copyright (c) 2018-2020 Red Hat, Inc.
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


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.profile, "NM") as m:
        yield m


@pytest.fixture
def NM_connection_mock():
    with mock.patch.object(nm.connection, "NM") as m:
        yield m


@pytest.fixture()
def context_mock():
    yield mock.MagicMock()


def test_create_profile(NM_mock, context_mock):
    settings = [11, 22]
    con_profile = nm.profile.Profile(context_mock)
    con_profile.create(settings)

    con_profile_mock = NM_mock.SimpleConnection.new.return_value

    con_profile_mock.add_setting.assert_has_calls(
        [mock.call(settings[0]), mock.call(settings[1])]
    )
    assert con_profile_mock == con_profile.profile


def test_add_profile(NM_mock, context_mock):
    con_profile = nm.profile.Profile(context_mock)
    con_profile.create([])
    con_profile.add()

    nm_add_conn2_flags = NM_mock.SettingsAddConnection2Flags
    flags = nm_add_conn2_flags.BLOCK_AUTOCONNECT
    flags |= nm_add_conn2_flags.TO_DISK

    user_data = f"Add profile: {con_profile.profile.get_id()}"

    context_mock.client.add_connection2.assert_called_once_with(
        profile.to_dbus(NM_mock.ConnectionSerializationFlags.ALL),
        flags,
        None,
        False,
        context_mock.cancellable,
        con_profile._add_connection2_callback,
        user_data,
    )


def test_update_profile(NM_mock, context_mock):
    new_profile_mock = mock.MagicMock()
    new_profile = nm.profile.Profile(context_mock, new_profile_mock)

    profile = mock.MagicMock()
    con_profile = nm.profile.Profile(context_mock, profile)
    con_profile.update(new_profile)
    user_data = f"Update profile: {profile.get_id()}"

    nm_update2_flags = NM_mock.SettingsUpdate2Flags
    flags = nm_update2_flags.BLOCK_AUTOCONNECT
    flags |= nm_update2_flags.TO_DISK
    profile.update2.assert_called_once_with(
        new_profile_mock.to_dbus(
            context_mock.NM.ConnectionSerializationFlags.ALL
        ),
        flags,
        None,
        context_mock.cancellable,
        con_profile._update2_callback,
        user_data,
    )


def test_create_setting(NM_connection_mock):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create("con-name", "iface-name", "iface-type")

    assert con_setting.setting.props.id == "con-name"
    assert con_setting.setting.props.interface_name == "iface-name"
    assert con_setting.setting.props.uuid
    assert con_setting.setting.props.type == "iface-type"
    assert con_setting.setting.props.autoconnect is True
    assert con_setting.setting.props.autoconnect_slaves == (
        NM_connection_mock.SettingConnectionAutoconnectSlaves.YES
    )


def test_duplicate_settings(NM_connection_mock):
    base_con_profile_mock = mock.MagicMock()

    new_con_setting = nm.connection.ConnectionSetting()
    new_con_setting.import_by_profile(base_con_profile_mock)

    base = base_con_profile_mock.profile.get_setting_connection.return_value
    new = new_con_setting.setting
    assert new.props.id == base.props.id
    assert new.props.interface_name == base.props.interface_name
    assert new.props.uuid == base.props.uuid
    assert new.props.type == base.props.type
    assert new.props.autoconnect is True
    assert new.props.autoconnect_slaves == base.props.autoconnect_slaves


def test_set_master_setting():
    con_setting = nm.connection.ConnectionSetting(mock.MagicMock())
    con_setting.set_master("master0", "slave-type")

    assert con_setting.setting.props.master == "master0"
    assert con_setting.setting.props.slave_type == "slave-type"


def test_get_device_connection(context_mock):
    dev_mock = mock.MagicMock()

    con = nm.profile.Profile(context_mock)
    con.import_by_device(dev_mock)

    assert (
        dev_mock.get_active_connection.return_value.props.connection
        == con.profile
    )
