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

from .compat import mock

from libnmstate import netinfo


@pytest.fixture
def nm_mock():
    with mock.patch.object(netinfo, 'nm') as m:
        yield m


def test_netinfo_show_generic_iface(nm_mock):
    current_config = {
        'interfaces': [
            {
                'name': 'foo',
                'type': 'unknown',
                'state': 'up',
                'ipv4': {
                    'enabled': False,
                },
            }
        ]
    }

    nm_mock.device.list_devices.return_value = ['one-item']
    nm_mock.translator.Nm2Api.get_common_device_info.return_value = (
        current_config['interfaces'][0])
    nm_mock.bond.is_bond_type_id.return_value = False
    nm_mock.ipv4.get_info.return_value = (
        current_config['interfaces'][0]['ipv4'])

    report = netinfo.show()

    assert current_config == report


def test_netinfo_show_bond_iface(nm_mock):
    current_config = {
        'interfaces': [
            {
                'name': 'bond99',
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': [],
                    'options': {
                        'miimon': '100',
                    }
                },
                'ipv4': {
                    'enabled': False,
                },
            }
        ]
    }

    nm_mock.device.list_devices.return_value = ['one-item']
    nm_mock.translator.Nm2Api.get_common_device_info.return_value = {
        'name': current_config['interfaces'][0]['name'],
        'type': current_config['interfaces'][0]['type'],
        'state': current_config['interfaces'][0]['state'],
    }
    nm_mock.bond.is_bond_type_id.return_value = True
    nm_mock.translator.Nm2Api.get_bond_info.return_value = {
        'link-aggregation': current_config['interfaces'][0]['link-aggregation']
    }
    nm_mock.ipv4.get_info.return_value = (
        current_config['interfaces'][0]['ipv4'])

    report = netinfo.show()

    assert current_config == report
