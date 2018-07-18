#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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
    profile = nm.connection.create_profile(settings)

    con_profile_mock = NM_mock.SimpleConnection.new.return_value

    con_profile_mock.add_setting.assert_has_calls(
        [mock.call(settings[0]), mock.call(settings[1])])
    assert con_profile_mock == profile


def test_add_profile(client_mock, mainloop_mock):
    save_to_disk = True
    nm.connection.add_profile('profile', save_to_disk)

    mainloop_mock.push_action.assert_called_once_with(
        client_mock.add_connection_async,
        'profile',
        save_to_disk,
        mainloop_mock.cancellable,
        nm.connection._add_connection_callback,
        mainloop_mock,
    )


def test_update_profile():
    base_profile = mock.MagicMock()

    nm.connection.update_profile(base_profile, 'p')

    base_profile.replace_settings_from_connection.assert_called_once_with('p')


def test_commit_profile(mainloop_mock):
    con_profile = mock.MagicMock()
    save_to_disk = True
    nm.connection.commit_profile(con_profile, save_to_disk)

    mainloop_mock.push_action.assert_called_once_with(
        con_profile.commit_changes_async,
        save_to_disk,
        mainloop_mock.cancellable,
        nm.connection._commit_changes_callback,
        mainloop_mock,
    )


def test_create_setting(NM_mock):
    con_setting = nm.connection.create_setting(
        'con-name', 'iface-name', 'iface-type')

    assert con_setting.props.id == 'con-name'
    assert con_setting.props.interface_name == 'iface-name'
    assert con_setting.props.uuid
    assert con_setting.props.type == 'iface-type'
    assert con_setting.props.autoconnect is True
    assert con_setting.props.autoconnect_slaves == (
        NM_mock.SettingConnectionAutoconnectSlaves.NO)


def test_duplicate_settings(NM_mock):
    base_con_profile_mock = mock.MagicMock()

    new_con = nm.connection.duplicate_settings(base_con_profile_mock)

    base_con = base_con_profile_mock.get_setting_connection.return_value

    assert new_con.props.id == base_con.props.id
    assert new_con.props.interface_name == base_con.props.interface_name
    assert new_con.props.uuid == base_con.props.uuid
    assert new_con.props.type == base_con.props.type
    assert new_con.props.autoconnect == base_con.props.autoconnect
    assert new_con.props.autoconnect_slaves == (
        base_con.props.autoconnect_slaves)


def test_set_master_setting():
    con_setting_mock = mock.MagicMock()

    nm.connection.set_master_setting(con_setting_mock, 'master0', 'slave-type')

    assert con_setting_mock.props.master == 'master0'
    assert con_setting_mock.props.slave_type == 'slave-type'


def test_get_device_connection():
    dev_mock = mock.MagicMock()

    con = nm.connection.get_device_connection(dev_mock)

    assert dev_mock.get_active_connection.return_value.props.connection == con
