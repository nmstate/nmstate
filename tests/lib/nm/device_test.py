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


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.device.nmclient, "NM") as m:
        yield m


@pytest.fixture()
def client_mock():
    with mock.patch.object(nm.device.nmclient, "client") as m:
        yield m.return_value


@pytest.fixture()
def mainloop_mock():
    with mock.patch.object(nm.device.nmclient, "mainloop") as m:
        yield m.return_value


@mock.patch.object(nm.device.connection, "ConnectionProfile")
def test_activate(con_profile_mock):
    dev = mock.MagicMock()
    con_profile = con_profile_mock()

    nm.device.activate(dev)

    con_profile.activate.assert_called_once()


@mock.patch.object(nm.device.ac, "ActiveConnection")
def test_deactivate(act_con_mock):
    dev = mock.MagicMock()
    act_con = act_con_mock()

    nm.device.deactivate(dev)

    assert act_con.nmdevice == dev
    act_con.deactivate.assert_called_once()


@mock.patch.object(nm.connection, "ConnectionProfile")
def test_delete(con_profile_mock):
    dev = mock.MagicMock()
    dev.get_available_connections.return_value = [mock.MagicMock()]
    con_profile = con_profile_mock()

    nm.device.delete(dev)

    con_profile.delete.assert_called_once()


def test_get_device_by_name(client_mock):
    devname = "foo"
    nm.device.get_device_by_name(devname)

    client_mock.get_device_by_iface.assert_called_once_with(devname)


def test_list_devices(client_mock):
    nm.device.list_devices()

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
