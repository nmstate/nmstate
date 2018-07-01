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


@pytest.fixture(scope='module')
def NM_mock():
    saved_api2nm_map = nm.translator.Api2Nm._iface_types_map
    saved_nm2api_map = nm.translator.Nm2Api._iface_types_map
    nm.translator.Api2Nm._iface_types_map = None
    nm.translator.Nm2Api._iface_types_map = None

    with mock.patch.object(nm.translator.nmclient, 'NM') as m:
        yield m

    nm.translator.Api2Nm._iface_types_map = saved_api2nm_map
    nm.translator.Nm2Api._iface_types_map = saved_nm2api_map


def test_api2nm_iface_type_map(NM_mock):
    map = nm.translator.Api2Nm.get_iface_type_map()

    expected_map = {
        'ethernet': NM_mock.SETTING_WIRED_SETTING_NAME,
        'bond': NM_mock.SETTING_BOND_SETTING_NAME,
        'dummy': NM_mock.SETTING_DUMMY_SETTING_NAME,
        'ovs-bridge': NM_mock.SETTING_OVS_BRIDGE_SETTING_NAME,
        'ovs-port': NM_mock.SETTING_OVS_PORT_SETTING_NAME,
        'ovs-interface': NM_mock.SETTING_OVS_INTERFACE_SETTING_NAME,
    }

    assert map == expected_map


def test_api2nm_get_iface_type(NM_mock):
    nm_type = nm.translator.Api2Nm.get_iface_type('ethernet')
    assert NM_mock.SETTING_WIRED_SETTING_NAME == nm_type


@mock.patch.object(nm.translator.Api2Nm, 'get_iface_type',
                   staticmethod(lambda t: t))
def test_api2nm_bond_options():
    bond_options = {
        'name': 'bond99',
        'type': 'bond',
        'state': 'up',
        'link-aggregation': {
            'mode': 'balance-rr',
            'options': {
                'miimon': 120
            }
        }
    }
    nm_bond_options = nm.translator.Api2Nm.get_bond_options(bond_options)

    assert {'miimon': 120, 'mode': 'balance-rr'} == nm_bond_options


def test_nm2api_common_device_info():
    devinfo = {
        'name': 'devname',
        'type_id': 'devtypeid',
        'type_name': 'devtypename',
        'state': 'devstate',
    }
    info = nm.translator.Nm2Api.get_common_device_info(devinfo)

    expected_info = {
        'name': 'devname',
        'state': 'down',
        'type': 'unknown',
    }
    assert expected_info == info


def test_nm2api_bond_info():
    slaves_mock = [mock.MagicMock(), mock.MagicMock()]
    bondinfo = {
        'slaves': slaves_mock,
        'options': {
            'mode': 'balance-rr',
            'miimon': 120,
        }
    }
    info = nm.translator.Nm2Api.get_bond_info(bondinfo)

    expected_info = {
        'link-aggregation':
            {
                'mode': 'balance-rr',
                'slaves': [slaves_mock[0].props.interface,
                           slaves_mock[1].props.interface],
                'options': {
                    'miimon': 120
                }
            }
    }
    assert expected_info == info


def test_iface_admin_state(NM_mock):
    NM_mock.DeviceState.ACTIVATED = 'ACTIVATED'
    admin_state = nm.translator.Nm2Api.get_iface_admin_state('ACTIVATED')

    assert nm.translator.ApiIfaceAdminState.UP == admin_state
