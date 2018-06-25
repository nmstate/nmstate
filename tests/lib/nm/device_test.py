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


@pytest.fixture()
def client_mock():
    with mock.patch.object(nm.device.nmclient, 'client') as m:
        yield m.return_value


def test_activate(client_mock):
    dev = 'foodev'
    nm.device.activate(dev)
    client_mock.activate_connection_async.assert_called_once_with(device=dev)


def test_deactivate(client_mock):
    dev = mock.MagicMock()
    nm.device.deactivate(dev)

    dev.get_active_connection.assert_called_once()
    client_mock.deactivate_connection_async.assert_called_once_with(
        dev.get_active_connection.return_value)


def test_delete():
    dev = mock.MagicMock()
    dev.get_available_connections.return_value = [mock.MagicMock()]
    nm.device.delete(dev)

    dev.get_available_connections.assert_called_once()
    connections = dev.get_available_connections.return_value
    connections[0].delete_async.assert_called_once()


def test_get_device_by_name(client_mock):
    devname = 'foo'
    nm.device.get_device_by_name(devname)

    client_mock.get_device_by_iface.assert_called_once_with(devname)


def test_list_devices(client_mock):
    nm.device.list_devices()

    client_mock.get_devices.assert_called_once()


def test_get_device_common_info():
    dev = mock.MagicMock()

    info = nm.device.get_device_common_info(dev)

    expected_info = {
        'name': dev.get_iface.return_value,
        'type_id': dev.get_device_type.return_value,
        'type_name': dev.get_type_description.return_value,
        'state': dev.get_state.return_value,
    }
    assert expected_info == info
