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
from libnmstate.error import NmstateDependencyError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Team

from .testlib import assertlib
from .testlib.nmplugin import disable_nm_plugin


TEAM0 = "team0"


pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Team kmod not available in Travis CI",
)


@pytest.mark.xfail(reason="https://bugzilla.redhat.com/1798947")
def test_create_team_iface():
    with team_interface(TEAM0) as team_state:
        assertlib.assert_state(team_state)


@pytest.mark.xfail(reason="https://bugzilla.redhat.com/1798947")
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
