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
def nm_bond_mock():
    with mock.patch.object(nm.applier, 'bond') as m:
        yield m


@pytest.fixture
def nm_connection_mock():
    with mock.patch.object(nm.applier, 'connection') as m:
        yield m


@pytest.fixture
def nm_device_mock():
    with mock.patch.object(nm.applier, 'device') as m:
        yield m


@pytest.fixture
def nm_ipv4_mock():
    with mock.patch.object(nm.applier, 'ipv4') as m:
        yield m


@pytest.fixture
def nm_ipv6_mock():
    with mock.patch.object(nm.applier, 'ipv6') as m:
        yield m


@pytest.fixture
def nm_ovs_mock():
    with mock.patch.object(nm.applier, 'ovs') as m:
        yield m


def test_create_new_ifaces(nm_connection_mock):
    con_profiles = ['profile1', 'profile2']

    nm.applier.create_new_ifaces(con_profiles)

    nm_connection_mock.add_profile.assert_has_calls(
        [
            mock.call(con_profiles[0], save_to_disk=True),
            mock.call(con_profiles[1], save_to_disk=True)
        ]
    )


@mock.patch.object(nm.translator.Api2Nm, 'get_iface_type',
                   staticmethod(lambda t: t))
def test_prepare_new_ifaces_configuration(nm_bond_mock,
                                          nm_connection_mock,
                                          nm_ipv4_mock,
                                          nm_ipv6_mock,
                                          nm_ovs_mock):
    nm_ovs_mock.translate_bridge_options.return_value = {}
    nm_ovs_mock.translate_port_options.return_value = {}

    ifaces_desired_state = [
        {
            'name': 'eth0',
            'type': 'ethernet',
            'state': 'up',
            '_master': 'bond99',
            '_master_type': 'bond'
        },
        {
            'name': 'bond99',
            'type': 'bond',
            'state': 'up',
            'link-aggregation': {
                'mode': 'balance-rr',
                'slaves': ['eth0'],
                'options': {
                    'miimon': 120
                }
            }
        }
    ]

    nm.applier.prepare_new_ifaces_configuration(ifaces_desired_state)

    con_setting = nm_connection_mock.create_setting.return_value
    nm_connection_mock.set_master_setting.assert_has_calls(
        [
            mock.call(con_setting, 'bond99', 'bond'),
            mock.call(con_setting, None, None)
        ],
        any_order=True
    )
    nm_connection_mock.create_profile.assert_has_calls(
        [
            mock.call([
                nm_ipv4_mock.create_setting.return_value,
                nm_ipv6_mock.create_setting.return_value,
                con_setting,
            ]),
            mock.call([
                nm_ipv4_mock.create_setting.return_value,
                nm_ipv6_mock.create_setting.return_value,
                con_setting,
                nm_bond_mock.create_setting.return_value,
            ])
        ]
    )


def test_edit_existing_ifaces_with_profile(nm_device_mock, nm_connection_mock):
    con_profiles = [mock.MagicMock(), mock.MagicMock()]

    nm.applier.edit_existing_ifaces(con_profiles)

    nm_connection_mock.commit_profile.assert_has_calls(
        [mock.call(con_profiles[0],
                   nmdev=nm_device_mock.get_device_by_name.return_value),
         mock.call(con_profiles[1],
                   nmdev=nm_device_mock.get_device_by_name.return_value)]
    )


def test_edit_existing_ifaces_without_profile(nm_device_mock,
                                              nm_connection_mock):
    con_profiles = [mock.MagicMock(), mock.MagicMock()]
    nm_connection_mock.get_device_connection.return_value = None

    nm.applier.edit_existing_ifaces(con_profiles)

    nm_connection_mock.add_profile.assert_has_calls(
        [
            mock.call(con_profiles[0], save_to_disk=True),
            mock.call(con_profiles[1], save_to_disk=True)
        ]
    )


@mock.patch.object(nm.translator.Api2Nm, 'get_iface_type',
                   staticmethod(lambda t: t))
def test_prepare_edited_ifaces_configuration(nm_device_mock,
                                             nm_connection_mock,
                                             nm_ipv4_mock,
                                             nm_ipv6_mock,
                                             nm_ovs_mock):
    nm_ovs_mock.translate_bridge_options.return_value = {}
    nm_ovs_mock.translate_port_options.return_value = {}

    ifaces_desired_state = [
        {
            'name': 'eth0',
            'type': 'ethernet',
            'state': 'up',
        }
    ]
    cons = nm.applier.prepare_edited_ifaces_configuration(ifaces_desired_state)

    assert len(cons) == 1

    nm_connection_mock.update_profile.assert_has_calls(
        [
            mock.call(nm_connection_mock.get_device_connection.return_value,
                      nm_connection_mock.create_profile.return_value),
        ]
    )


class TestIfaceAdminStateControl(object):
    def test_set_ifaces_admin_state_up(self, nm_device_mock):
        ifaces_desired_state = [
            {
                'name': 'eth0',
                'type': 'ethernet',
                'state': 'up',
            }
        ]
        nm.applier.set_ifaces_admin_state(ifaces_desired_state)

        nm_device_mock.activate.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value)

    def test_set_ifaces_admin_state_down(self, nm_device_mock):
        ifaces_desired_state = [
            {
                'name': 'eth0',
                'type': 'ethernet',
                'state': 'down',
            }
        ]
        nm.applier.set_ifaces_admin_state(ifaces_desired_state)

        nm_device_mock.deactivate.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value)
        nm_device_mock.delete.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value)

    def test_set_ifaces_admin_state_absent(self, nm_device_mock):
        ifaces_desired_state = [
            {
                'name': 'eth0',
                'type': 'ethernet',
                'state': 'absent',
            }
        ]
        nm.applier.set_ifaces_admin_state(ifaces_desired_state)

        nm_device_mock.deactivate.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value)
        nm_device_mock.delete.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value)

    def test_set_bond_and_its_slaves_admin_state_up(self,
                                                    nm_device_mock,
                                                    nm_bond_mock):
        ifaces_desired_state = [
            {
                'name': 'bond0',
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': '802.3ad',
                    'slaves': ['eth0']
                },
            },
            {
                'name': 'eth0',
                'type': 'ethernet',
                'state': 'up',
            }
        ]

        nm_device_mock.get_device_by_name = lambda devname: devname
        bond = ifaces_desired_state[0]['name']
        slaves = ifaces_desired_state[0]['link-aggregation']['slaves']
        nm_bond_mock.BOND_TYPE = nm.bond.BOND_TYPE
        nm_bond_mock.get_slaves.return_value = slaves

        nm.applier.set_ifaces_admin_state(ifaces_desired_state)

        expected_calls = [
            mock.call(bond),
            mock.call(slaves[0])
        ]
        actual_calls = nm_device_mock.activate.mock_calls
        assert sorted(expected_calls) == sorted(actual_calls)
