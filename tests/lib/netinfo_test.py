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

from .compat import mock

from libnmstate import netinfo


NM_DEVICE_STATE_UNKNOWN = 0
NM_DEVICE_TYPE_BOND = 10
NM_DEVICE_TYPE_GENERIC = 14


@mock.patch.object(netinfo.nmclient, 'NM')
@mock.patch.object(netinfo.nm.device.nmclient, 'client')
def test_netinfo_show(mock_client, mock_nm):
    mock_client.return_value.get_devices.return_value = [
        MockNmDevice('lo'),
        MockNmDevice('bond99', type_id=NM_DEVICE_TYPE_BOND)
    ]
    mock_nm.DeviceType.BOND = NM_DEVICE_TYPE_BOND

    report = netinfo.show()
    iface_names = [iface['name'] for iface in report['interfaces']]
    assert 'lo' in iface_names
    assert 'bond99' in iface_names


class MockNmDevice(object):

    def __init__(self, name, type_id=NM_DEVICE_TYPE_GENERIC):
        self._name = name
        self._type_id = type_id

    def get_iface(self):
        return self._name

    def get_device_type(self):
        return self._type_id

    def get_type_description(self):
        return 'Generic device'

    def get_state(self):
        return NM_DEVICE_STATE_UNKNOWN

    def get_active_connection(self):
        return mock.MagicMock()

    def get_slaves(self):
        return []
