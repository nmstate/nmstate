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
    with mock.patch.object(nm.ovs.nmclient, 'NM') as m:
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
        options['mcast-snooping-enable']
    )
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
