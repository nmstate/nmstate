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
    with mock.patch.object(nm.ovs.nmclient, 'NM') as m:
        yield m


@pytest.fixture
def nm_connection_mock():
    with mock.patch.object(nm.ovs, 'connection') as m:
        yield m


@pytest.fixture
def nm_device_mock():
    with mock.patch.object(nm.ovs, 'device') as m:
        yield m


def test_is_ovs_bridge_type_id(NM_mock):
    type_id = NM_mock.DeviceType.OVS_BRIDGE
    assert nm.ovs.is_ovs_bridge_type_id(type_id)


def test_is_ovs_port_type_id(NM_mock):
    type_id = NM_mock.DeviceType.OVS_PORT
    assert nm.ovs.is_ovs_port_type_id(type_id)


def test_is_ovs_interface_type_id(NM_mock):
    type_id = NM_mock.DeviceType.OVS_INTERFACE
    assert nm.ovs.is_ovs_interface_type_id(type_id)


def test_get_ovs_info_without_ports(nm_connection_mock, NM_mock):
    bridge_device = mock.MagicMock()
    _mock_port_profile(nm_connection_mock)

    device_info = [(bridge_device, None)]
    info = nm.ovs.get_ovs_info(bridge_device, device_info)

    expected_info = {
        'port': [],
        'options': {
            'fail-mode': '',
            'mcast-snooping-enable': False,
            'rstp': False,
            'stp': False
        },
    }
    assert expected_info == info


def test_get_ovs_info_with_ports_without_interfaces(nm_connection_mock,
                                                    nm_device_mock,
                                                    NM_mock):
    bridge_device = mock.MagicMock()
    port_device = mock.MagicMock()
    _mock_port_profile(nm_connection_mock)
    active_con = nm_connection_mock.get_device_active_connection.return_value
    active_con.props.master = bridge_device

    device_info = [(bridge_device, None), (port_device, None)]
    info = nm.ovs.get_ovs_info(bridge_device, device_info)

    expected_info = {
        'port': [],
        'options': {
            'fail-mode': '',
            'mcast-snooping-enable': False,
            'rstp': False,
            'stp': False
        },
    }
    assert expected_info == info


def test_get_ovs_info_with_ports_with_interfaces(nm_connection_mock,
                                                 nm_device_mock,
                                                 NM_mock):
    bridge_device = mock.MagicMock()
    port_device = mock.MagicMock()
    bridge_active_con = mock.MagicMock()
    port_active_con = mock.MagicMock()
    nm_device_mock.get_device_by_name.return_value = port_device
    _mock_port_profile(nm_connection_mock)
    nm_connection_mock.get_device_active_connection = (
        lambda dev:
        bridge_active_con if dev == bridge_device else port_active_con
    )
    bridge_active_con.props.master = bridge_device
    port_active_con.props.master = port_device

    device_info = [(bridge_device, None), (port_device, None)]
    info = nm.ovs.get_ovs_info(bridge_device, device_info)

    assert len(info['port']) == 1
    assert 'name' in info['port'][0]
    assert 'type' in info['port'][0]
    assert 'vlan-mode' in info['port'][0]
    assert 'access-tag' in info['port'][0]


def test_create_bridge_setting(NM_mock):
    options = {
        'fail-mode': 'foo',
        'mcast-snooping-enable': False,
        'rstp': False,
        'stp': False,
    }
    bridge_setting = nm.ovs.create_bridge_setting(options)

    assert bridge_setting.props.fail_mode == options['fail-mode']
    assert bridge_setting.props.mcast_snooping_enable == (
        options['mcast-snooping-enable'])
    assert bridge_setting.props.rstp_enable == options['rstp']
    assert bridge_setting.props.stp_enable == options['stp']


def test_create_port_setting(NM_mock):
    options = {
        'tag': 101,
        'vlan-mode': 'voomode',
        'bond-mode': 'boomode',
        'lacp': 'yes',
        'bond-updelay': 0,
        'bond-downdelay': 0,
    }
    port_setting = nm.ovs.create_port_setting(options)

    assert port_setting.props.tag == options['tag']
    assert port_setting.props.vlan_mode == options['vlan-mode']
    assert port_setting.props.bond_mode == options['bond-mode']
    assert port_setting.props.lacp == options['lacp']
    assert port_setting.props.bond_updelay == options['bond-updelay']
    assert port_setting.props.bond_downdelay == options['bond-downdelay']


def _mock_port_profile(nm_connection_mock):
    connection_profile = nm_connection_mock.get_device_connection.return_value
    bridge_setting = connection_profile.get_setting.return_value
    bridge_setting.props.stp_enable = False
    bridge_setting.props.rstp_enable = False
    bridge_setting.props.fail_mode = None
    bridge_setting.props.mcast_snooping_enable = False
