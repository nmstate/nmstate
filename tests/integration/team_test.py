#
# Copyright (c) 2019 Red Hat, Inc.
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
from libnmstate.error import NmstateLibnmError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Team

from .testlib import assertlib
from .testlib import cmdlib


DNF_INSTALL_NM_TEAM_PLUGIN_CMD = (
    "dnf",
    "install",
    "-y",
    "--cacheonly",
    "NetworkManager-team",
)

DNF_REMOVE_NM_TEAM_PLUGIN_CMD = (
    "dnf",
    "remove",
    "-y",
    "-q",
    "NetworkManager-team",
)

SYSTEMCTL_RESTART_NM_CMD = ("systemctl", "restart", "NetworkManager")

TEAM0 = "team0"


pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Team kmod not available in Travis CI",
)


def test_create_team_iface():
    with team_interface(TEAM0) as team_state:
        assertlib.assert_state(team_state)


def test_edit_team_iface():
    with team_interface(TEAM0) as team_state:
        team_state[Interface.KEY][0][Team.CONFIG_SUBTREE] = {
            Team.RUNNER_SUBTREE: {
                Team.Runner.NAME: Team.Runner.RunnerMode.LOAD_BALANCE
            },
            Team.PORT_SUBTREE: [{Team.Port.NAME: "eth1"}],
        }
        libnmstate.apply(team_state)
        assertlib.assert_state(team_state)


def test_nm_team_plugin_missing():
    with disable_nm_team_plugin():
        with pytest.raises(NmstateLibnmError):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: TEAM0,
                            Interface.TYPE: InterfaceType.TEAM,
                            Interface.STATE: InterfaceState.UP,
                        }
                    ]
                }
            )


@contextmanager
def team_interface(ifname):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.TEAM,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ifname,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )


@contextmanager
def disable_nm_team_plugin():
    cmdlib.exec_cmd(DNF_REMOVE_NM_TEAM_PLUGIN_CMD)
    cmdlib.exec_cmd(SYSTEMCTL_RESTART_NM_CMD)
    try:
        yield
    finally:
        cmdlib.exec_cmd(DNF_INSTALL_NM_TEAM_PLUGIN_CMD)
        cmdlib.exec_cmd(SYSTEMCTL_RESTART_NM_CMD)
