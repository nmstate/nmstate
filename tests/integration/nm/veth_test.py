#
# Copyright (c) 2021 Red Hat, Inc.
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

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from ..testlib.env import nm_major_minor_version
from ..testlib import cmdlib
from ..testlib.veth import veth_interface


VETH1 = "veth1"
VETH1PEER = "veth1peer"


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
def test_remove_peer_connection():
    with veth_interface(VETH1, VETH1PEER) as desired_state:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)
        assert (
            cmdlib.exec_cmd(f"nmcli connection show {VETH1PEER}".split())[0]
            != 0
        )
