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

import pytest

import libnmstate

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import OVSBridge
from libnmstate.error import NmstateLibnmError

from .testlib import statelib
from .testlib import assertlib
from .testlib.ovslib import Bridge


BRIDGE1 = 'br1'
PORT1 = 'ovs1'


@pytest.mark.xfail(
    raises=NmstateLibnmError, reason='https://bugzilla.redhat.com/1724901'
)
def test_create_and_remove_ovs_bridge_with_min_desired_state():
    with Bridge(BRIDGE1).create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.xfail(
    raises=NmstateLibnmError, reason='https://bugzilla.redhat.com/1724901'
)
def test_create_and_remove_ovs_bridge_options_specified():
    bridge = Bridge(BRIDGE1)
    bridge.set_options(
        {
            OVSBridge.FAIL_MODE: '',
            OVSBridge.MCAST_SNOOPING_ENABLED: False,
            OVSBridge.RSTP: False,
            OVSBridge.STP: True,
        }
    )

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.xfail(
    raises=NmstateLibnmError, reason='https://bugzilla.redhat.com/1724901'
)
def test_create_and_remove_ovs_bridge_with_a_system_port(port0_up):
    bridge = Bridge(BRIDGE1)
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge.add_system_port(port0_name)

    with bridge.create() as state:
        assertlib.assert_state_match(state)

        filtered_state = statelib.filter_current_state(state)
        assert Interface.MAC in filtered_state['interfaces'][0]

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.xfail(
    raises=NmstateLibnmError, reason='https://bugzilla.redhat.com/1724901'
)
def test_create_and_remove_ovs_bridge_with_internal_port_and_static_ip():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        PORT1,
        {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: '192.0.2.1',
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        },
    )

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)
