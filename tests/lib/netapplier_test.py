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
import copy

import pytest

from unittest import mock

from libnmstate import netapplier
from libnmstate.schema import Constants
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

INTERFACES = Constants.INTERFACES
BOND_TYPE = 'bond'


@pytest.fixture(scope='module', autouse=True)
def nmclient_mock():
    client_mock = mock.patch.object(netapplier.nmclient, 'client')
    mainloop_mock = mock.patch.object(netapplier.nmclient, 'mainloop')
    with client_mock, mainloop_mock:
        yield


@pytest.fixture
def netapplier_nm_mock():
    with mock.patch.object(netapplier, 'nm') as m:
        m.applier.prepare_proxy_ifaces_desired_state.return_value = []
        yield m


@pytest.fixture
def netinfo_nm_mock():
    with mock.patch.object(netapplier.netinfo, 'nm') as m:
        yield m


def test_iface_admin_state_change(netinfo_nm_mock, netapplier_nm_mock):
    current_config = {
        INTERFACES: [
            {
                'name': 'foo',
                'type': 'unknown',
                'state': 'up',
                'ipv4': {InterfaceIPv4.ENABLED: False},
                'ipv6': {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    desired_config = copy.deepcopy(current_config)

    current_iface0 = current_config[INTERFACES][0]
    netinfo_nm_mock.device.list_devices.return_value = ['one-item']
    netinfo_nm_mock.translator.Nm2Api.get_common_device_info.return_value = (
        current_iface0
    )
    netinfo_nm_mock.bond.is_bond_type_id.return_value = False
    netinfo_nm_mock.ovs.is_ovs_bridge_type_id.return_value = False
    netinfo_nm_mock.ovs.is_ovs_port_type_id.return_value = False
    netinfo_nm_mock.ipv4.get_info.return_value = current_iface0['ipv4']
    netinfo_nm_mock.ipv6.get_info.return_value = current_iface0['ipv6']
    netinfo_nm_mock.ipv4.get_route_running.return_value = []
    netinfo_nm_mock.ipv4.get_route_config.return_value = []
    netinfo_nm_mock.ipv6.get_route_running.return_value = []
    netinfo_nm_mock.ipv6.get_route_config.return_value = []

    desired_config[INTERFACES][0]['state'] = 'down'
    netapplier.apply(desired_config, verify_change=False)

    applier_mock = netapplier_nm_mock.applier
    ifaces_conf_new = (
        applier_mock.prepare_new_ifaces_configuration.return_value
    )
    ifaces_conf_edit = (
        applier_mock.prepare_edited_ifaces_configuration.return_value
    )
    applier_mock.set_ifaces_admin_state.assert_has_calls(
        [
            mock.call(
                desired_config[INTERFACES],
                con_profiles=ifaces_conf_new + ifaces_conf_edit,
            )
        ]
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
                'name': 'bond99',
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': [],
                    'options': {'miimon': 200},
                },
                'ipv4': {},
                'ipv6': {},
            }
        ]
    }

    netapplier.apply(desired_config, verify_change=False)

    m_prepare = netapplier_nm_mock.applier.prepare_edited_ifaces_configuration
    m_prepare.assert_called_once_with([])

    m_prepare = netapplier_nm_mock.applier.prepare_new_ifaces_configuration
    m_prepare.assert_called_once_with(desired_config[INTERFACES])


def test_edit_existing_bond(netinfo_nm_mock, netapplier_nm_mock):
    current_config = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': [],
                    'options': {'miimon': '100'},
                },
                'ipv4': {InterfaceIPv4.ENABLED: False},
                'ipv6': {InterfaceIPv6.ENABLED: False},
            }
        ]
    }

    current_iface0 = current_config[INTERFACES][0]
    netinfo_nm_mock.device.list_devices.return_value = ['one-item']
    netinfo_nm_mock.translator.Nm2Api.get_common_device_info.return_value = {
        'name': current_iface0['name'],
        'type': current_iface0['type'],
        'state': current_iface0['state'],
    }
    netinfo_nm_mock.bond.is_bond_type_id.return_value = True
    netinfo_nm_mock.translator.Nm2Api.get_bond_info.return_value = {
        'link-aggregation': current_iface0['link-aggregation']
    }
    netinfo_nm_mock.ipv4.get_info.return_value = current_iface0['ipv4']
    netinfo_nm_mock.ipv6.get_info.return_value = current_iface0['ipv6']
    netinfo_nm_mock.ipv4.get_route_running.return_value = []
    netinfo_nm_mock.ipv4.get_route_config.return_value = []
    netinfo_nm_mock.ipv6.get_route_running.return_value = []
    netinfo_nm_mock.ipv6.get_route_config.return_value = []

    desired_config = copy.deepcopy(current_config)
    options = desired_config[INTERFACES][0]['link-aggregation']['options']
    options['miimon'] = 200

    netapplier.apply(desired_config, verify_change=False)

    m_prepare = netapplier_nm_mock.applier.prepare_edited_ifaces_configuration
    m_prepare.assert_called_once_with(desired_config[INTERFACES])

    m_prepare = netapplier_nm_mock.applier.prepare_new_ifaces_configuration
    m_prepare.assert_called_once_with([])
