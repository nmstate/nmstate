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

import pytest

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from ..testlib import statelib
from ..testlib import cmdlib


BRIDGE0 = "brtest0"


@pytest.fixture
def ovs_unmanaged_bridge():
    cmdlib.exec_cmd(f"ovs-vsctl add-br {BRIDGE0}".split())
    yield
    cmdlib.exec_cmd(f"ovs-vsctl del-br {BRIDGE0}".split())


@pytest.mark.tier1
def test_do_not_show_unmanaged_ovs_bridge(ovs_unmanaged_bridge):
    # The output should only contains the OVS internal interface
    ovs_internal_iface = statelib.show_only((BRIDGE0,))[Interface.KEY][0]
    assert ovs_internal_iface[Interface.TYPE] == InterfaceType.OVS_INTERFACE
