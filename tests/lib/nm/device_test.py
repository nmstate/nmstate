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
from unittest import mock

import pytest

from libnmstate import nm


@pytest.fixture()
def client_mock():
    yield mock.MagicMock()


@pytest.fixture()
def con_profile_mock():
    with mock.patch.object(nm.device.connection, "ConnectionProfile") as m:
        yield m


@pytest.fixture()
def act_con_mock():
    with mock.patch.object(nm.device.ac, "ActiveConnection") as m:
        yield m


def test_activate(client_mock, con_profile_mock):
    dev = mock.MagicMock()
    con_profile = con_profile_mock(client_mock)

    nm.device.activate(client_mock, dev)

    con_profile.activate.assert_called_once()


def test_deactivate(client_mock, act_con_mock):
    dev = mock.MagicMock()
    act_con = act_con_mock()

    nm.device.deactivate(client_mock, dev)

    assert act_con.nmdevice == dev
    act_con.deactivate.assert_called_once()


def test_delete(client_mock, con_profile_mock):
    dev = mock.MagicMock()
    dev.get_available_connections.return_value = [mock.MagicMock()]
    con_profile = con_profile_mock(client_mock)

    nm.device.delete(client_mock, dev)

    con_profile.delete.assert_called_once()


def test_get_device_by_name(client_mock):
    devname = "foo"
    nm.device.get_device_by_name(client_mock, devname)

    client_mock.get_device_by_iface.assert_called_once_with(devname)


def test_list_devices(client_mock):
    nm.device.list_devices(client_mock)

    client_mock.get_devices.assert_called_once()


def test_get_device_common_info():
    dev = mock.MagicMock()

    info = nm.device.get_device_common_info(dev)

    expected_info = {
        "name": dev.get_iface.return_value,
        "type_id": dev.get_device_type.return_value,
        "type_name": dev.get_type_description.return_value,
        "state": dev.get_state.return_value,
    }
    assert expected_info == info
