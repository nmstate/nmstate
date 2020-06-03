#
# Copyright (c) 2020 Red Hat, Inc.
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

from libnmstate.schema import Team
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.team import TeamIface

from ..testlib.ifacelib import gen_foo_iface_info

SLAVE1_IFACE_NAME = "slave1"
SLAVE2_IFACE_NAME = "slave2"


class TestTeamIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.TEAM)
        iface_info[Team.CONFIG_SUBTREE] = {
            Team.PORT_SUBTREE: [
                {Team.Port.NAME: SLAVE1_IFACE_NAME},
                {Team.Port.NAME: SLAVE2_IFACE_NAME},
            ],
            Team.RUNNER_SUBTREE: {
                Team.Runner.NAME: Team.Runner.RunnerMode.LOAD_BALANCE
            },
        }
        return iface_info

    def test_team_is_virtual(self):
        assert TeamIface(self._gen_iface_info()).is_virtual

    def test_team_is_master(self):
        assert TeamIface(self._gen_iface_info()).is_master

    def test_team_sort_slaves(self):
        iface1_info = self._gen_iface_info()
        iface2_info = self._gen_iface_info()
        iface2_info[Team.CONFIG_SUBTREE][Team.PORT_SUBTREE].reverse()

        iface1 = TeamIface(iface1_info)
        iface2 = TeamIface(iface2_info)

        assert iface1.state_for_verify() == iface2.state_for_verify()

    def test_team_remove_slave(self):
        iface_info = self._gen_iface_info()
        iface_info[Team.CONFIG_SUBTREE][Team.PORT_SUBTREE].pop()

        iface = TeamIface(iface_info)
        assert iface.slaves == [SLAVE1_IFACE_NAME]
