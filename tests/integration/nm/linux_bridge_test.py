#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge as LB

from ..testlib.bridgelib import linux_bridge
from ..testlib.dummy import nm_unmanaged_dummy


BRIDGE0 = "brtest0"
DUMMY1 = "dummy1"


@pytest.fixture
def nm_unmanaged_dummy1():
    with nm_unmanaged_dummy(DUMMY1):
        yield


@pytest.mark.tier1
def test_bridge_as_port_unmanaged_interface(nm_unmanaged_dummy1):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}}
        },
    ) as desired_state:
        bridge_iface_state = desired_state[Interface.KEY][0]
        bridge_iface_state[LB.CONFIG_SUBTREE] = {
            LB.PORT_SUBTREE: [{LB.Port.NAME: DUMMY1}],
        }
        # To reproduce bug https://bugzilla.redhat.com/1816517
        # explitly define dummy1 as IPv4/IPv6 disabled is required.
        desired_state[Interface.KEY].append(
            {
                Interface.NAME: DUMMY1,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        )
        libnmstate.apply(desired_state)
