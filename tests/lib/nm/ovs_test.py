#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
from libnmstate.schema import OVSBridge


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.ovs, "NM") as m:
        yield m


@pytest.fixture
def context_mock():
    yield mock.MagicMock()


@pytest.fixture
def nm_connection_mock():
    with mock.patch.object(nm.ovs, "connection") as m:
        yield m


def test_is_ovs_port_type_id(NM_mock):
    type_id = NM_mock.DeviceType.OVS_PORT
    assert nm.ovs.is_ovs_port_type_id(type_id)


def test_get_ovs_bridge_info_without_ports(NM_mock):
    bridge_device = mock.MagicMock()
    _mock_ovs_bridge_profile(bridge_device)

    info = nm.ovs.get_ovs_bridge_info(bridge_device)

    expected_info = {
        OVSBridge.CONFIG_SUBTREE: {
            OVSBridge.PORT_SUBTREE: [],
            OVSBridge.OPTIONS_SUBTREE: {
                OVSBridge.Options.FAIL_MODE: "",
                OVSBridge.Options.MCAST_SNOOPING_ENABLED: False,
                OVSBridge.Options.RSTP: False,
                OVSBridge.Options.STP: False,
            },
        }
    }
    assert expected_info == info


def test_get_ovs_bridge_info_without_interfaces(NM_mock):
    bridge_device = mock.MagicMock()
    port_device = mock.MagicMock()
    _mock_ovs_bridge_profile(bridge_device)
    bridge_device.get_slaves.return_value = [port_device]
    port_device.get_slaves.return_value = []

    info = nm.ovs.get_ovs_bridge_info(bridge_device)

    expected_info = {
        OVSBridge.CONFIG_SUBTREE: {
            OVSBridge.PORT_SUBTREE: [],
            OVSBridge.OPTIONS_SUBTREE: {
                OVSBridge.Options.FAIL_MODE: "",
                OVSBridge.Options.MCAST_SNOOPING_ENABLED: False,
                OVSBridge.Options.RSTP: False,
                OVSBridge.Options.STP: False,
            },
        }
    }
    assert expected_info == info


def test_get_ovs_bridge_info_with_ports_with_interfaces(NM_mock):
    bridge_device = mock.MagicMock()
    port_device = mock.MagicMock()
    iface_device = mock.MagicMock()
    _mock_ovs_bridge_profile(bridge_device)
    bridge_device.get_slaves.return_value = [port_device]
    port_device.get_slaves.return_value = [iface_device]

    ovs_info = nm.ovs.get_ovs_bridge_info(bridge_device)[
        OVSBridge.CONFIG_SUBTREE
    ]

    assert len(ovs_info[OVSBridge.PORT_SUBTREE]) == 1
    port_state = ovs_info[OVSBridge.PORT_SUBTREE][0]
    assert OVSBridge.Port.NAME in port_state
    vlan_state = port_state[OVSBridge.Port.VLAN_SUBTREE]
    assert OVSBridge.Port.Vlan.MODE in vlan_state
    assert OVSBridge.Port.Vlan.TAG not in vlan_state


def test_create_bridge_setting(NM_mock):
    options = {
        OVSBridge.Options.FAIL_MODE: "foo",
        OVSBridge.Options.MCAST_SNOOPING_ENABLED: False,
        OVSBridge.Options.RSTP: False,
        OVSBridge.Options.STP: False,
    }
    bridge_setting = nm.ovs.create_bridge_setting(options)

    assert (
        bridge_setting.props.fail_mode == options[OVSBridge.Options.FAIL_MODE]
    )
    assert bridge_setting.props.mcast_snooping_enable == (
        options[OVSBridge.Options.MCAST_SNOOPING_ENABLED]
    )
    assert bridge_setting.props.rstp_enable == options[OVSBridge.Options.RSTP]
    assert bridge_setting.props.stp_enable == options[OVSBridge.Options.STP]


def test_create_port_setting(NM_mock):
    mode = OVSBridge.Port.LinkAggregation.Mode.BALANCE_TCP
    updelay = 1
    downdelay = 2
    vlan_mode = OVSBridge.Port.Vlan.Mode.ACCESS
    vlan_tag = 2
    options = {
        OVSBridge.Port.LINK_AGGREGATION_SUBTREE: {
            OVSBridge.Port.LinkAggregation.MODE: mode,
            OVSBridge.Port.LinkAggregation.Options.UP_DELAY: updelay,
            OVSBridge.Port.LinkAggregation.Options.DOWN_DELAY: downdelay,
        },
        OVSBridge.Port.VLAN_SUBTREE: {
            OVSBridge.Port.Vlan.MODE: vlan_mode,
            OVSBridge.Port.Vlan.TAG: vlan_tag,
        },
    }

    port_setting = nm.ovs.create_port_setting(options)

    assert port_setting.props.bond_mode == mode
    assert port_setting.props.lacp == nm.ovs.LacpValue.ACTIVE
    assert port_setting.props.bond_updelay == updelay
    assert port_setting.props.bond_downdelay == downdelay
    assert port_setting.props.tag == vlan_tag
    assert port_setting.props.vlan_mode == vlan_mode


def _mock_ovs_bridge_profile(bridge_device):
    act_con = bridge_device.get_active_connection.return_value
    conn = act_con.props.connection
    bridge_setting = conn.get_setting.return_value
    bridge_setting.props.stp_enable = False
    bridge_setting.props.rstp_enable = False
    bridge_setting.props.fail_mode = None
    bridge_setting.props.mcast_snooping_enable = False
