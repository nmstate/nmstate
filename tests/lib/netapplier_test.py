#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

import pytest

from .compat import mock

from libnmstate import netapplier


UP = 1
DOWN = 0


@pytest.fixture()
def config():
    return {
        'interfaces': [
            {'name': 'foo', 'type': 'unknown', 'state': 'up'}
        ]
    }


@mock.patch.object(netapplier.nmclient, 'NM')
@mock.patch.object(netapplier.nmclient, 'client')
class TestDevStateChange(object):
    def test_apply_iface_state_up_to_up(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=UP)
        mk_nm.DeviceState.ACTIVATED = UP

        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_not_called()
        mk_client.return_value.deactivate_connection_async.assert_not_called()

    def test_apply_iface_state_down_to_up(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=DOWN)
        mk_nm.DeviceState.ACTIVATED = UP

        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_called_once()
        mk_client.return_value.deactivate_connection_async.assert_not_called()

    def test_apply_iface_state_down_to_down(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=DOWN)
        mk_nm.DeviceState.ACTIVATED = UP

        config['interfaces'][0]['state'] = 'down'
        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_not_called()
        mk_client.return_value.deactivate_connection_async.assert_not_called()

    def test_apply_iface_state_up_to_down(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(
            devstate=UP, active_connection='con0')
        mk_nm.DeviceState.ACTIVATED = UP

        config['interfaces'][0]['state'] = 'down'
        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_not_called()
        mk_client.return_value.deactivate_connection_async.assert_called_once()


class MockNmDevice(object):

    def __init__(self, devstate, active_connection=None):
        self._state = devstate
        self._active_connection = active_connection

    def get_active_connection(self):
        return self._active_connection

    def get_state(self):
        return self._state
