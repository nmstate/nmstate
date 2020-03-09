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
import copy

import pytest

from unittest import mock

from libnmstate import netapplier
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Constants
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.state import State

INTERFACES = Constants.INTERFACES
BOND_TYPE = InterfaceType.BOND


@pytest.fixture(scope="module", autouse=True)
def nmclient_mock():
    client_mock = mock.patch.object(netapplier.nmclient, "client")
    mainloop_mock = mock.patch.object(netapplier.nmclient, "mainloop")
    with client_mock, mainloop_mock:
        yield


@pytest.fixture
def netapplier_nm_mock():
    with mock.patch.object(netapplier, "nm") as m:
        m.applier.prepare_proxy_ifaces_desired_state.return_value = []
        yield m


@pytest.fixture
def netinfo_nm_mock():
    with mock.patch.object(netapplier.netinfo, "nm") as m:
        m.ipv4.get_routing_rule_config.return_value = []
        m.ipv6.get_routing_rule_config.return_value = []
        yield m


def test_iface_admin_state_change(netinfo_nm_mock, netapplier_nm_mock):
    current_config = {
        INTERFACES: [
            {
                Interface.NAME: "foo",
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    desired_config = copy.deepcopy(current_config)

    current_iface0 = current_config[INTERFACES][0]
    netinfo_nm_mock.device.list_devices.return_value = ["one-item"]
    netinfo_nm_mock.translator.Nm2Api.get_common_device_info.return_value = (
        current_iface0
    )
    netinfo_nm_mock.bond.is_bond_type_id.return_value = False
    netinfo_nm_mock.ovs.is_ovs_bridge_type_id.return_value = False
    netinfo_nm_mock.ovs.is_ovs_port_type_id.return_value = False
    netinfo_nm_mock.ipv4.get_info.return_value = current_iface0[Interface.IPV4]
    netinfo_nm_mock.ipv6.get_info.return_value = current_iface0[Interface.IPV6]
    netinfo_nm_mock.ipv4.get_route_running.return_value = []
    netinfo_nm_mock.ipv4.get_route_config.return_value = []
    netinfo_nm_mock.ipv6.get_route_running.return_value = []
    netinfo_nm_mock.ipv6.get_route_config.return_value = []

    desired_config[INTERFACES][0][Interface.STATE] = InterfaceState.DOWN
    netapplier.apply(desired_config, verify_change=False)

    applier_mock = netapplier_nm_mock.applier
    applier_mock.apply_changes.assert_has_calls(
        [mock.call(desired_config[INTERFACES], State(desired_config))]
    )


def test_add_new_bond(netinfo_nm_mock, netapplier_nm_mock):
    netinfo_nm_mock.device.list_devices.return_value = []
    netinfo_nm_mock.ipv4.get_route_running.return_value = []
    netinfo_nm_mock.ipv4.get_route_config.return_value = []
    netinfo_nm_mock.ipv6.get_route_running.return_value = []
    netinfo_nm_mock.ipv6.get_route_config.return_value = []

    desired_config = {
        INTERFACES: [
            {
                Interface.NAME: "bond99",
                Interface.TYPE: BOND_TYPE,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.SLAVES: [],
                    Bond.OPTIONS_SUBTREE: {"miimon": 200},
                },
                Interface.IPV4: {},
                Interface.IPV6: {},
            }
        ]
    }

    netapplier.apply(desired_config, verify_change=False)

    m_apply_changes = netapplier_nm_mock.applier.apply_changes
    m_apply_changes.assert_called_once_with(
        desired_config[INTERFACES], State(desired_config)
    )


def test_edit_existing_bond(netinfo_nm_mock, netapplier_nm_mock):
    current_config = {
        INTERFACES: [
            {
                Interface.NAME: "bond99",
                Interface.TYPE: BOND_TYPE,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.SLAVES: [],
                    Bond.OPTIONS_SUBTREE: {"miimon": "100"},
                },
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }

    current_iface0 = current_config[INTERFACES][0]
    netinfo_nm_mock.device.list_devices.return_value = ["one-item"]
    netinfo_nm_mock.translator.Nm2Api.get_common_device_info.return_value = {
        Interface.NAME: current_iface0[Interface.NAME],
        Interface.TYPE: current_iface0[Interface.TYPE],
        Interface.STATE: current_iface0[Interface.STATE],
    }
    netinfo_nm_mock.bond.is_bond_type_id.return_value = True
    netinfo_nm_mock.translator.Nm2Api.get_bond_info.return_value = {
        Bond.CONFIG_SUBTREE: current_iface0[Bond.CONFIG_SUBTREE]
    }
    netinfo_nm_mock.ipv4.get_info.return_value = current_iface0[Interface.IPV4]
    netinfo_nm_mock.ipv6.get_info.return_value = current_iface0[Interface.IPV6]
    netinfo_nm_mock.ipv4.get_route_running.return_value = []
    netinfo_nm_mock.ipv4.get_route_config.return_value = []
    netinfo_nm_mock.ipv6.get_route_running.return_value = []
    netinfo_nm_mock.ipv6.get_route_config.return_value = []

    desired_config = copy.deepcopy(current_config)
    options = desired_config[INTERFACES][0][Bond.CONFIG_SUBTREE][
        Bond.OPTIONS_SUBTREE
    ]
    options["miimon"] = 200

    netapplier.apply(desired_config, verify_change=False)

    m_apply_changes = netapplier_nm_mock.applier.apply_changes
    m_apply_changes.assert_called_once_with(
        desired_config[INTERFACES], State(desired_config)
    )


@mock.patch.object(netapplier, "_apply_ifaces_state", lambda *_: None)
def test_warning_apply():
    with pytest.warns(FutureWarning) as record:
        netapplier.apply({"interfaces": []}, True)

    assert len(record) == 1
    assert "'verify_change'" in record[0].message.args[0]

    with pytest.warns(FutureWarning) as record:
        netapplier.apply({"interfaces": []}, True, True, 0)

    assert len(record) == 3
    assert "'verify_change'" in record[0].message.args[0]
    assert "'commit'" in record[1].message.args[0]
    assert "'rollback_timeout'" in record[2].message.args[0]


@mock.patch.object(netapplier, "_choose_checkpoint", lambda *_: mock.Mock())
def test_warning_commit():
    with pytest.warns(FutureWarning) as record:
        netapplier.commit(None)

    assert len(record) == 1
    assert "'checkpoint'" in record[0].message.args[0]


@mock.patch.object(netapplier, "_choose_checkpoint", lambda *_: mock.Mock())
def test_warning_rollback():
    with pytest.warns(FutureWarning) as record:
        netapplier.rollback(None)

    assert len(record) == 1
    assert "'checkpoint'" in record[0].message.args[0]
