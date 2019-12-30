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
    nm_ovs_mock.translate_bridge_options.return_value = {}
    nm_ovs_mock.translate_port_options.return_value = {}

    ifaces_desired_state = [
        {
            "name": "eth0",
            "type": "ethernet",
            "state": "up",
            metadata.MASTER: "bond99",
            metadata.MASTER_TYPE: "bond",
        },
        {
            "name": "bond99",
            "type": "bond",
            "state": "up",
            "link-aggregation": {
                "mode": "balance-rr",
                "slaves": ["eth0"],
                "options": {"miimon": 120},
            },
        },
    ]

    ctx = mock.MagicMock()
    nm.applier.prepare_new_ifaces_configuration(ctx, ifaces_desired_state)

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
    ctx = mock.MagicMock()

    nm.applier.edit_existing_ifaces(ctx, con_profiles)

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

    ctx = mock.MagicMock()
    nm.applier.edit_existing_ifaces(ctx, con_profiles)

    for con_profile in con_profiles:
        con_profile.add.assert_has_calls([mock.call(save_to_disk=True)])


@mock.patch.object(
    nm.translator.Api2Nm, "get_iface_type", staticmethod(lambda t: t)
)
def test_prepare_edited_ifaces_configuration(
    nm_device_mock, nm_connection_mock, nm_ipv4_mock, nm_ipv6_mock, nm_ovs_mock
):
    nm_ovs_mock.translate_bridge_options.return_value = {}
    nm_ovs_mock.translate_port_options.return_value = {}

    ifaces_desired_state = [
        {"name": "eth0", "type": "ethernet", "state": "up"}
    ]
    ctx = mock.MagicMock()
    cons = nm.applier.prepare_edited_ifaces_configuration(
        ctx, ifaces_desired_state
    )

    assert len(cons) == 1

    con_profile = nm_connection_mock.ConnectionProfile.return_value
    con_profile.update.assert_has_calls([mock.call(con_profile)])


class TestIfaceAdminStateControl:
    def test_set_ifaces_admin_state_up(self, nm_device_mock):
        ifaces_desired_state = [
            {"name": "eth0", "type": "ethernet", "state": "up"}
        ]
        con_profile = mock.MagicMock()
        con_profile.devname = ifaces_desired_state[0]["name"]
        ctx = mock.MagicMock()
        nm.applier.set_ifaces_admin_state(
            ctx, ifaces_desired_state, [con_profile]
        )

        nm_device_mock.modify.assert_called_once_with(
            ctx,
            nm_device_mock.get_device_by_name.return_value,
            con_profile.profile,
        )

    def test_set_ifaces_admin_state_down(self, nm_device_mock):
        ifaces_desired_state = [
            {"name": "eth0", "type": "ethernet", "state": "down"}
        ]
        ctx = mock.MagicMock()
        nm.applier.set_ifaces_admin_state(ctx, ifaces_desired_state)

        nm_device_mock.deactivate.assert_called_once_with(
            ctx, nm_device_mock.get_device_by_name.return_value
        )
        nm_device_mock.delete.assert_called_once_with(
            ctx, nm_device_mock.get_device_by_name.return_value
        )

    def test_set_ifaces_admin_state_absent(self, nm_device_mock):
        ifaces_desired_state = [
            {"name": "eth0", "type": "ethernet", "state": "absent"}
        ]
        ctx = mock.MagicMock()
        nm.applier.set_ifaces_admin_state(ctx, ifaces_desired_state)

        nm_device_mock.deactivate.assert_called_once_with(
            ctx, nm_device_mock.get_device_by_name.return_value
        )
        nm_device_mock.delete.assert_called_once_with(
            ctx, nm_device_mock.get_device_by_name.return_value
        )

    def test_set_bond_and_its_slaves_admin_state_up(
        self, nm_device_mock, nm_bond_mock
    ):
        ifaces_desired_state = [
            {
                "name": "bond0",
                "type": "bond",
                "state": "up",
                "link-aggregation": {"mode": "802.3ad", "slaves": ["eth0"]},
            },
            {"name": "eth0", "type": "ethernet", "state": "up"},
        ]

        nm_device_mock.get_device_by_name = lambda ctx, devname: devname
        bond = ifaces_desired_state[0]["name"]
        slaves = ifaces_desired_state[0]["link-aggregation"]["slaves"]
        nm_bond_mock.BOND_TYPE = nm.bond.BOND_TYPE
        nm_bond_mock.get_slaves.return_value = slaves

        bond_con_profile = mock.MagicMock()
        bond_con_profile.devname = ifaces_desired_state[0]["name"]
        slave_con_profile = mock.MagicMock()
        slave_con_profile.devname = ifaces_desired_state[1]["name"]

        ctx = mock.MagicMock()

        nm.applier.set_ifaces_admin_state(
            ctx, ifaces_desired_state, [bond_con_profile, slave_con_profile]
        )

        expected_calls = [
            mock.call(ctx, bond, bond_con_profile.profile),
            mock.call(ctx, slaves[0], slave_con_profile.profile),
        ]
        actual_calls = nm_device_mock.modify.mock_calls
        assert sorted(expected_calls) == sorted(actual_calls)
