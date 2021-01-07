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
import json
import os

import pytest

import libnmstate
from libnmstate.error import NmstateDependencyError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Team
from libnmstate.error import NmstateValueError

from .testlib import assertlib
from .testlib import statelib
from .testlib.cmdlib import exec_cmd
from .testlib.cmdlib import RC_SUCCESS
from .testlib.nmplugin import disable_nm_plugin


TEAM0 = "team0"
PORT1 = "eth1"
PORT2 = "eth2"


pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Team kmod not available in Travis CI",
)


def test_create_team_iface_without_port():
    with team_interface(TEAM0) as team_state:
        assertlib.assert_state(team_state)


@pytest.mark.tier1
def test_create_team_iface_with_port(eth1_up, eth2_up):
    with team_interface(TEAM0, [PORT1, PORT2]) as team_state:
        assertlib.assert_state_match(team_state)
        assert [PORT1, PORT2] == _get_runtime_team_port(TEAM0)
    assertlib.assert_absent(TEAM0)


def test_edit_team_iface(eth1_up):
    with team_interface(TEAM0) as team_state:
        team_state[Interface.KEY][0][Team.CONFIG_SUBTREE] = {
            Team.RUNNER_SUBTREE: {
                Team.Runner.NAME: Team.Runner.RunnerMode.LOAD_BALANCE
            },
            Team.PORT_SUBTREE: [{Team.Port.NAME: "eth1"}],
        }
        libnmstate.apply(team_state)
        assertlib.assert_state_match(team_state)


def test_nm_team_plugin_missing():
    with disable_nm_plugin("team"):
        with pytest.raises(NmstateDependencyError):
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


def test_add_invalid_port_ip_config(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.ENABLED] = True
    desired_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.DHCP] = True
    with pytest.raises(NmstateValueError):
        with team_interface(TEAM0, ports=("eth1",)) as state:
            desired_state[Interface.KEY].append(state[Interface.KEY][0])
            libnmstate.apply(desired_state)


@contextmanager
def team_interface(ifname, ports=None):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.TEAM,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    if ports:
        team_state = {Team.PORT_SUBTREE: []}
        desired_state[Interface.KEY][0][Team.CONFIG_SUBTREE] = team_state
        for port in ports:
            team_state[Team.PORT_SUBTREE].append({Team.Port.NAME: port})
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


def _get_runtime_team_port(team_iface_name):
    """
    Use `teamdctl team0 state dump` to check team runtime status
    """
    rc, output, _ = exec_cmd(f"teamdctl {team_iface_name} state dump".split())
    assert rc == RC_SUCCESS
    teamd_state = json.loads(output)
    return sorted(teamd_state.get("ports", {}).keys())


def test_team_change_port_order(eth1_up, eth2_up):
    with team_interface(TEAM0, [PORT1, PORT2]) as desired_state:
        desired_state[Interface.KEY][0][Team.CONFIG_SUBTREE][
            Team.PORT_SUBTREE
        ].reverse()
        libnmstate.apply(desired_state)


@pytest.fixture
def team0_up(eth1_up, eth2_up):
    with team_interface(TEAM0, [PORT1, PORT2]):
        yield


def test_show_saved_config_with_team_down(team0_up):
    running_state = statelib.show_only((TEAM0,))
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEAM0,
                    Interface.STATE: InterfaceState.DOWN,
                }
            ]
        }
    )
    saved_state = statelib.show_saved_config_only((TEAM0,))

    assert saved_state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
    assertlib.assert_state_match_full(saved_state, running_state)
