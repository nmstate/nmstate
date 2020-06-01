#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from contextlib import contextmanager
import os


import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import statelib


DUMMY0_IFNAME = "dummy0"

NMCLI_CON_ADD_DUMMY_CMD = [
    "nmcli",
    "con",
    "add",
    "type",
    "dummy",
    "con-name",
    "testProfile",
    "connection.autoconnect",
    "no",
    "ifname",
    DUMMY0_IFNAME,
]

NMCLI_CON_ADD_ETH_CMD = [
    "nmcli",
    "con",
    "add",
    "type",
    "ethernet",
    "con-name",
    "testProfile",
    "connection.autoconnect",
    "no",
    "ifname",
    "eth1",
]

NMCLI_CON_UP_TEST_PROFILE_CMD = [
    "nmcli",
    "con",
    "up",
    "testProfile",
]

DUMMY_PROFILE_DIRECTORY = "/etc/NetworkManager/system-connections/"

ETH_PROFILE_DIRECTORY = "/etc/sysconfig/network-scripts/"

MEMORY_ONLY_PROFILE_DIRECTORY = "/run/NetworkManager/system-connections/"

MAC0 = "02:FF:FF:FF:FF:00"


@pytest.mark.tier1
def test_delete_new_interface_inactive_profiles(dummy_inactive_profile):
    with dummy_interface(dummy_inactive_profile):
        profile_exists = _profile_exists(
            DUMMY_PROFILE_DIRECTORY + "testProfile.nmconnection"
        )
        assert not profile_exists


@pytest.mark.tier1
def test_delete_existing_interface_inactive_profiles(eth1_up):
    with create_inactive_profile(eth1_up[Interface.KEY][0][Interface.NAME]):
        eth1_up[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(eth1_up)
        profile_exists = _profile_exists(
            ETH_PROFILE_DIRECTORY + "ifcfg-testProfile"
        )
        assert not profile_exists


def test_rename_existing_interface_active_profile(eth1_up):
    cloned_profile_name = "testProfile"
    with cloned_active_profile(
        cloned_profile_name, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        eth1_up[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(eth1_up)
        assert _profile_exists(ETH_PROFILE_DIRECTORY + "ifcfg-testProfile")


@contextmanager
def dummy_interface(ifname, save_to_disk=True):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state, save_to_disk=save_to_disk)
    try:
        yield desired_state
    finally:
        dummy0_dstate = desired_state[Interface.KEY][0]
        dummy0_dstate[Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)


@pytest.fixture
def dummy_inactive_profile():
    cmdlib.exec_cmd(NMCLI_CON_ADD_DUMMY_CMD)
    profile_exists = _profile_exists(
        DUMMY_PROFILE_DIRECTORY + "testProfile.nmconnection"
    )
    assert profile_exists
    try:
        yield DUMMY0_IFNAME
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection("testProfile"))


@contextmanager
def cloned_active_profile(con_name, source):
    cmdlib.exec_cmd(["nmcli", "con", "clone", "id", source, con_name])
    cmdlib.exec_cmd(_nmcli_delete_connection(source))
    cmdlib.exec_cmd(NMCLI_CON_UP_TEST_PROFILE_CMD)
    profile_exists = _profile_exists(
        ETH_PROFILE_DIRECTORY + f"ifcfg-{con_name}"
    )
    assert profile_exists
    try:
        yield
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection(con_name))


@contextmanager
def create_inactive_profile(con_name):
    cmdlib.exec_cmd(_nmcli_deactivate_connection(con_name))
    cmdlib.exec_cmd(NMCLI_CON_ADD_ETH_CMD)
    profile_exists = _profile_exists(
        ETH_PROFILE_DIRECTORY + "ifcfg-testProfile"
    )
    assert profile_exists
    try:
        yield
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection("testProfile"))


def test_state_down_preserving_config():
    with dummy_interface(DUMMY0_IFNAME) as desired_state:
        iface_state = desired_state[Interface.KEY][0]
        iface_state[Interface.MAC] = MAC0
        iface_state[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
        libnmstate.apply(desired_state)
        state_before_down = statelib.show_only((DUMMY0_IFNAME,))

        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DUMMY0_IFNAME,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )

        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DUMMY0_IFNAME,
                        Interface.TYPE: InterfaceType.DUMMY,
                        Interface.STATE: InterfaceState.UP,
                    }
                ]
            }
        )

        assertlib.assert_state_match(state_before_down)


@pytest.fixture
def dummy0_with_down_profile():
    with dummy_interface(DUMMY0_IFNAME) as desired_state:
        iface_state = desired_state[Interface.KEY][0]
        iface_state[Interface.MAC] = MAC0
        iface_state[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
        libnmstate.apply(desired_state)
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DUMMY0_IFNAME,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )
        yield desired_state


def test_state_absent_can_remove_down_profiles(dummy0_with_down_profile):
    state_before_down = dummy0_with_down_profile
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0_IFNAME,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0_IFNAME,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
    )

    # Sinec absent already removed the down profile, if we bring the same
    # interface up, it should contain different states than before
    with pytest.raises(AssertionError):
        assertlib.assert_state_match(state_before_down)


def test_create_memory_only_profile_new_interface():
    with dummy_interface(DUMMY0_IFNAME, save_to_disk=False):
        assert _profile_exists(
            MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )

    assert not _profile_exists(
        MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
    )


def test_create_memory_only_profile_edit_interface():
    with dummy_interface(DUMMY0_IFNAME) as dstate:
        assert not _profile_exists(
            MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )
        dstate[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(dstate, save_to_disk=False)
        assert _profile_exists(
            MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )

    assert not _profile_exists(
        MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
    )


@pytest.mark.xfail(
    raises=AssertionError,
    reason="Showing virtual down interfaces is not possible yet",
    strict=True,
)
def test_memory_only_profile_absent_interface():
    with dummy_interface(DUMMY0_IFNAME) as dstate:
        dstate[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(dstate, save_to_disk=False)
        assertlib.assert_down(DUMMY0_IFNAME)

    assertlib.assert_absent(DUMMY0_IFNAME)


def _nmcli_deactivate_connection(con_name):
    return ["nmcli", "con", "down", con_name]


def _nmcli_delete_connection(con_name):
    return ["nmcli", "con", "delete", con_name]


def _profile_exists(profile_name):
    return os.path.isfile(profile_name)
