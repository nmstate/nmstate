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
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType


@pytest.fixture(scope="module")
def NM_mock():
    saved_api2nm_map = nm.translator.Api2Nm._iface_types_map
    saved_nm2api_map = nm.translator.Nm2Api._iface_types_map
    nm.translator.Api2Nm._iface_types_map = None
    nm.translator.Nm2Api._iface_types_map = None

    with mock.patch.object(nm.translator, "NM") as m:
        yield m

    nm.translator.Api2Nm._iface_types_map = saved_api2nm_map
    nm.translator.Nm2Api._iface_types_map = saved_nm2api_map


def test_api2nm_iface_type_map(NM_mock):
    ovs_interface_setting = NM_mock.SETTING_OVS_INTERFACE_SETTING_NAME
    map = nm.translator.Api2Nm.get_iface_type_map()

    expected_map = {
        InterfaceType.ETHERNET: NM_mock.SETTING_WIRED_SETTING_NAME,
        InterfaceType.BOND: NM_mock.SETTING_BOND_SETTING_NAME,
        InterfaceType.DUMMY: NM_mock.SETTING_DUMMY_SETTING_NAME,
        InterfaceType.OVS_BRIDGE: NM_mock.SETTING_OVS_BRIDGE_SETTING_NAME,
        InterfaceType.OVS_PORT: NM_mock.SETTING_OVS_PORT_SETTING_NAME,
        InterfaceType.OVS_INTERFACE: ovs_interface_setting,
        InterfaceType.TEAM: NM_mock.SETTING_TEAM_SETTING_NAME,
        InterfaceType.VLAN: NM_mock.SETTING_VLAN_SETTING_NAME,
        InterfaceType.LINUX_BRIDGE: NM_mock.SETTING_BRIDGE_SETTING_NAME,
        InterfaceType.VXLAN: NM_mock.SETTING_VXLAN_SETTING_NAME,
    }

    assert map == expected_map


def test_api2nm_get_iface_type(NM_mock):
    nm_type = nm.translator.Api2Nm.get_iface_type(InterfaceType.ETHERNET)
    assert NM_mock.SETTING_WIRED_SETTING_NAME == nm_type


@mock.patch.object(
    nm.translator.Api2Nm, "get_iface_type", staticmethod(lambda t: t)
)
def test_api2nm_bond_options():
    bond_options = {
        Interface.NAME: "bond99",
        Interface.TYPE: InterfaceType.BOND,
        Interface.STATE: InterfaceState.UP,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.OPTIONS_SUBTREE: {"miimon": 120},
        },
    }
    nm_bond_options = nm.translator.Api2Nm.get_bond_options(bond_options)

    assert {"miimon": 120, Bond.MODE: BondMode.ROUND_ROBIN} == nm_bond_options


def test_nm2api_common_device_info(NM_mock):
    NM_mock.DeviceState.ACTIVATED = 100
    NM_mock.DeviceState.IP_CONFIG = 70
    nm.common.NM.DeviceState.DISCONNECTED = 30
    devinfo = {
        "name": "devname",
        "type_id": "devtypeid",
        "type_name": "devtypename",
        "state": nm.common.NM.DeviceState.DISCONNECTED,
    }
    info = nm.translator.Nm2Api.get_common_device_info(devinfo)

    expected_info = {
        Interface.NAME: "devname",
        Interface.STATE: InterfaceState.DOWN,
        Interface.TYPE: InterfaceType.UNKNOWN,
    }
    assert expected_info == info


def test_nm2api_bond_info():
    slaves_mock = [mock.MagicMock(), mock.MagicMock()]
    bondinfo = {
        Bond.PORT: slaves_mock,
        Bond.OPTIONS_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN, "miimon": 120},
    }
    info = nm.translator.Nm2Api.get_bond_info(bondinfo)

    expected_info = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.PORT: [
                slaves_mock[0].props.interface,
                slaves_mock[1].props.interface,
            ],
            Bond.OPTIONS_SUBTREE: {"miimon": 120},
        }
    }
    assert expected_info == info


def test_iface_admin_state(NM_mock):
    NM_mock.DeviceState.ACTIVATED = 100
    NM_mock.DeviceState.IP_CONFIG = 70
    NM_mock.DeviceState.IP_CHECK = 80
    admin_state = nm.translator.Nm2Api.get_iface_admin_state(
        NM_mock.DeviceState.IP_CHECK
    )

    assert InterfaceState.UP == admin_state
