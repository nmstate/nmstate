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

from lib.compat import mock

from libnmstate import nm


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.connection.nmclient, 'NM') as m:
        yield m


@pytest.fixture()
def client_mock():
    with mock.patch.object(nm.connection.nmclient, 'client') as m:
        yield m.return_value


@pytest.fixture()
def mainloop_mock():
    with mock.patch.object(nm.connection.nmclient, 'mainloop') as m:
        yield m.return_value


def test_create_profile(NM_mock):
    settings = [11, 22]
    con_profile = nm.connection.ConnectionProfile()
    con_profile.create(settings)

    con_profile_mock = NM_mock.SimpleConnection.new.return_value

    con_profile_mock.add_setting.assert_has_calls(
        [mock.call(settings[0]), mock.call(settings[1])]
    )
    assert con_profile_mock == con_profile.profile


def test_add_profile(client_mock, mainloop_mock):
    save_to_disk = True
    con_profile = nm.connection.ConnectionProfile('profile')
    con_profile.add(save_to_disk)

    mainloop_mock.push_action.assert_called_once_with(
        client_mock.add_connection_async,
        'profile',
        save_to_disk,
        mainloop_mock.cancellable,
        nm.connection.ConnectionProfile._add_connection_callback,
        mainloop_mock,
    )


def test_update_profile():
    base_profile = nm.connection.ConnectionProfile('p')

    profile = mock.MagicMock()
    con_profile = nm.connection.ConnectionProfile(profile)
    con_profile.update(base_profile)

    profile.replace_settings_from_connection.assert_called_once_with('p')


def test_commit_profile(mainloop_mock):
    profile = mock.MagicMock()
    save_to_disk = True
    con_profile = nm.connection.ConnectionProfile(profile)
    con_profile.commit(save_to_disk)

    mainloop_mock.push_action.assert_called_once_with(
        profile.commit_changes_async,
        save_to_disk,
        mainloop_mock.cancellable,
        nm.connection.ConnectionProfile._commit_changes_callback,
        (mainloop_mock, None),
    )


def test_create_setting(NM_mock):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create('con-name', 'iface-name', 'iface-type')

    assert con_setting.setting.props.id == 'con-name'
    assert con_setting.setting.props.interface_name == 'iface-name'
    assert con_setting.setting.props.uuid
    assert con_setting.setting.props.type == 'iface-type'
    assert con_setting.setting.props.autoconnect is True
    assert con_setting.setting.props.autoconnect_slaves == (
        NM_mock.SettingConnectionAutoconnectSlaves.YES
    )


def test_duplicate_settings(NM_mock):
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
    con_setting.set_master('master0', 'slave-type')

    assert con_setting.setting.props.master == 'master0'
    assert con_setting.setting.props.slave_type == 'slave-type'


def test_get_device_connection():
    dev_mock = mock.MagicMock()

    con = nm.connection.ConnectionProfile()
    con.import_by_device(dev_mock)

    assert (
        dev_mock.get_active_connection.return_value.props.connection
        == con.profile
    )
