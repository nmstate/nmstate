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
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .testlib import cmdlib


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

DUMMY_PROFILE_DIRECTORY = "/etc/NetworkManager/system-connections/"

ETH_PROFILE_DIRECTORY = "/etc/sysconfig/network-scripts/"


def test_delete_new_interface_inactive_profiles(dummy_inactive_profile):
    with dummy_interface(dummy_inactive_profile):
        profile_exists = _profile_exists(
            DUMMY_PROFILE_DIRECTORY + "testProfile.nmconnection"
        )
        assert not profile_exists


def test_delete_existing_interface_inactive_profiles(eth1_up):
    with create_inactive_profile(eth1_up[Interface.KEY][0][Interface.NAME]):
        eth1_up[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(eth1_up)
        profile_exists = _profile_exists(
            ETH_PROFILE_DIRECTORY + "ifcfg-testProfile"
        )
        assert not profile_exists


@contextmanager
def dummy_interface(ifname):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)
    try:
        yield
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


def _nmcli_deactivate_connection(con_name):
    return ["nmcli", "con", "down", con_name]


def _nmcli_delete_connection(con_name):
    return ["nmcli", "con", "delete", con_name]


def _profile_exists(profile_name):
    return os.path.isfile(profile_name)
