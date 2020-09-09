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

import time

import pytest

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from ..testlib import cmdlib

BOND99 = "bond99"
DUMMY1 = "dummy1"
DUMMY2 = "dummy2"


@pytest.fixture
def bond99_with_dummy_slaves_by_iproute():
    cmdlib.exec_cmd(f"ip link add {DUMMY1} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link add {DUMMY2} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link add {BOND99} type bond".split(), check=True)
    cmdlib.exec_cmd(
        f"ip link set {DUMMY1} master {BOND99}".split(), check=True
    )
    cmdlib.exec_cmd(
        f"ip link set {DUMMY2} master {BOND99}".split(), check=True
    )
    cmdlib.exec_cmd(f"ip link set {DUMMY1} up".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {DUMMY2} up".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {BOND99} up".split(), check=True)
    time.sleep(1)  # Wait NM mark them as managed
    yield
    cmdlib.exec_cmd(f"nmcli c del {BOND99}".split())
    cmdlib.exec_cmd(f"nmcli c del {DUMMY1}".split())
    cmdlib.exec_cmd(f"nmcli c del {DUMMY2}".split())
    cmdlib.exec_cmd(f"ip link del {DUMMY1}".split())
    cmdlib.exec_cmd(f"ip link del {DUMMY2}".split())
    cmdlib.exec_cmd(f"ip link del {BOND99}".split())


def test_external_managed_subordnates(bond99_with_dummy_slaves_by_iproute):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND99,
                    Interface.STATE: InterfaceState.UP,
                    Bond.CONFIG_SUBTREE: {
                        # Change the bond mode to force a reactivate
                        Bond.MODE: BondMode.ACTIVE_BACKUP,
                        Bond.PORT: [DUMMY1, DUMMY2],
                    },
                }
            ]
        }
    )
