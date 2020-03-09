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

from libnmstate import metadata
from libnmstate import nm
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.state import State


@pytest.fixture
def nm_bond_mock():
    with mock.patch.object(nm.applier, "bond") as m:
        yield m


@pytest.fixture
def nm_connection_mock():
    with mock.patch.object(nm.applier, "connection") as m:
        yield m


@pytest.fixture
def nm_device_mock():
    with mock.patch.object(nm.applier, "device") as m:
        yield m


@pytest.fixture
def nm_ipv4_mock():
    with mock.patch.object(nm.applier, "ipv4") as m:
        yield m


@pytest.fixture
def nm_ipv6_mock():
    with mock.patch.object(nm.applier, "ipv6") as m:
        yield m


@pytest.fixture
def nm_ovs_mock():
    with mock.patch.object(nm.applier, "ovs") as m:
        yield m


@mock.patch.object(nm.connection, "ConnectionProfile")
def test_create_new_ifaces(con_profile_mock):
    con_profiles = [con_profile_mock(), con_profile_mock()]

    nm.applier.create_new_ifaces(con_profiles)

    for con_profile in con_profiles:
        con_profile.add.assert_has_calls([mock.call(save_to_disk=True)])


@mock.patch.object(
    nm.translator.Api2Nm, "get_iface_type", staticmethod(lambda t: t)
)
def test_prepare_new_ifaces_configuration(
    nm_bond_mock, nm_connection_mock, nm_ipv4_mock, nm_ipv6_mock, nm_ovs_mock
):
    ifaces_desired_state = [
        {
            Interface.NAME: "eth0",
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.STATE: InterfaceState.UP,
            metadata.MASTER: "bond99",
            metadata.MASTER_TYPE: InterfaceType.BOND,
        },
        {
            Interface.NAME: "bond99",
            Interface.TYPE: InterfaceType.BOND,
            Interface.STATE: InterfaceState.UP,
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ROUND_ROBIN,
                Bond.SLAVES: ["eth0"],
                Bond.OPTIONS_SUBTREE: {"miimon": 120},
            },
        },
    ]

    nm.applier.prepare_new_ifaces_configuration(ifaces_desired_state)

    con_setting = nm_connection_mock.ConnectionSetting.return_value
    con_setting.set_master.assert_has_calls(
        [mock.call("bond99", "bond"), mock.call(None, None)], any_order=True
    )
    con_profile = nm_connection_mock.ConnectionProfile.return_value
    con_profile.create.assert_has_calls(
        [
            mock.call(
                [
                    nm_ipv4_mock.create_setting.return_value,
                    nm_ipv6_mock.create_setting.return_value,
                    con_setting.setting,
                ]
            ),
            mock.call(
                [
                    nm_ipv4_mock.create_setting.return_value,
                    nm_ipv6_mock.create_setting.return_value,
                    con_setting.setting,
                    nm_bond_mock.create_setting.return_value,
                ]
            ),
        ]
    )


@mock.patch.object(nm.connection, "ConnectionProfile")
def test_edit_existing_ifaces_with_profile(con_profile_mock, nm_device_mock):
    con_profiles = [con_profile_mock(), con_profile_mock()]

    nm.applier.edit_existing_ifaces(con_profiles)

    for con_profile in con_profiles:
        con_profile.commit.assert_has_calls(
            [mock.call(nmdev=nm_device_mock.get_device_by_name.return_value)]
        )


@mock.patch.object(nm.connection, "ConnectionProfile")
def test_edit_existing_ifaces_without_profile(
    con_profile_mock, nm_device_mock
):
    con_profiles = [mock.MagicMock(), mock.MagicMock()]
    con_profile_mock.return_value.profile = None

    nm.applier.edit_existing_ifaces(con_profiles)

    for con_profile in con_profiles:
        con_profile.add.assert_has_calls([mock.call(save_to_disk=True)])


@mock.patch.object(
    nm.translator.Api2Nm, "get_iface_type", staticmethod(lambda t: t)
)
def test_prepare_edited_ifaces_configuration(
    nm_device_mock, nm_connection_mock, nm_ipv4_mock, nm_ipv6_mock, nm_ovs_mock
):
    ifaces_desired_state = [
        {
            Interface.NAME: "eth0",
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.STATE: InterfaceState.UP,
        }
    ]
    cons = nm.applier.prepare_edited_ifaces_configuration(
        ifaces_desired_state, State({Interface.KEY: ifaces_desired_state})
    )

    assert len(cons) == 1

    con_profile = nm_connection_mock.ConnectionProfile.return_value
    con_profile.update.assert_has_calls([mock.call(con_profile)])


class TestIfaceAdminStateControl:
    def test_set_ifaces_admin_state_up(self, nm_device_mock):
        ifaces_desired_state = [
            {
                Interface.NAME: "eth0",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
            }
        ]
        con_profile = mock.MagicMock()
        con_profile.devname = ifaces_desired_state[0][Interface.NAME]
        nm.applier.set_ifaces_admin_state(ifaces_desired_state, [con_profile])

        nm_device_mock.modify.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value, con_profile.profile
        )

    def test_set_ifaces_admin_state_down(self, nm_device_mock):
        ifaces_desired_state = [
            {
                Interface.NAME: "eth0",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.DOWN,
            }
        ]
        nm.applier.set_ifaces_admin_state(ifaces_desired_state)

        nm_device_mock.deactivate.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value
        )
        nm_device_mock.delete.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value
        )

    def test_set_ifaces_admin_state_absent(self, nm_device_mock):
        ifaces_desired_state = [
            {
                Interface.NAME: "eth0",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.ABSENT,
            }
        ]
        nm.applier.set_ifaces_admin_state(ifaces_desired_state)

        nm_device_mock.deactivate.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value
        )
        nm_device_mock.delete.assert_called_once_with(
            nm_device_mock.get_device_by_name.return_value
        )

    def test_set_bond_and_its_slaves_admin_state_up(
        self, nm_device_mock, nm_bond_mock
    ):
        ifaces_desired_state = [
            {
                Interface.NAME: "bond0",
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.LACP,
                    Bond.SLAVES: ["eth0"],
                },
            },
            {
                Interface.NAME: "eth0",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
            },
        ]

        nm_device_mock.get_device_by_name = lambda devname: devname
        bond = ifaces_desired_state[0][Interface.NAME]
        slaves = ifaces_desired_state[0][Bond.CONFIG_SUBTREE][Bond.SLAVES]
        nm_bond_mock.BOND_TYPE = nm.bond.BOND_TYPE
        nm_bond_mock.get_slaves.return_value = slaves

        bond_con_profile = mock.MagicMock()
        bond_con_profile.devname = ifaces_desired_state[0][Interface.NAME]
        slave_con_profile = mock.MagicMock()
        slave_con_profile.devname = ifaces_desired_state[1][Interface.NAME]

        nm.applier.set_ifaces_admin_state(
            ifaces_desired_state, [bond_con_profile, slave_con_profile]
        )

        expected_calls = [
            mock.call(bond, bond_con_profile.profile),
            mock.call(slaves[0], slave_con_profile.profile),
        ]
        actual_calls = nm_device_mock.modify.mock_calls
        assert sorted(expected_calls) == sorted(actual_calls)
