#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from contextlib import contextmanager
from copy import deepcopy

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge

from .testlib import assertlib
from .testlib.iproutelib import ip_monitor_assert_stable_link_up
from .testlib.statelib import show_only
from .testlib.statelib import INTERFACES

TEST_BRIDGE0 = 'linux-br0'
TEST_BRIDGE0_PORT0 = 'eth1'
TEST_BRIDGE0_PORT1 = 'eth2'


BRIDGE_OPTIONS_YAML = """
options:
  group-forward-mask: 0
  mac-ageing-time: 300
  multicast-snooping: true
  stp:
    enabled: true
    forward-delay: 15
    hello-time: 2
    max-age: 20
    priority: 32768
"""

BRIDGE_PORT_YAML = """
stp-hairpin-mode: false
stp-path-cost: 100
stp-priority: 32
"""


@pytest.fixture
def bridge0_with_port0(port0_up):
    bridge_name = TEST_BRIDGE0
    bridge_state = _create_bridge_subtree_config(('eth1',))
    # Disable STP to avoid topology changes and the consequence link change.
    options_subtree = bridge_state[LinuxBridge.OPTIONS_SUBTREE]
    options_subtree[LinuxBridge.STP_SUBTREE][LinuxBridge.STP_ENABLED] = False

    with _linux_bridge(bridge_name, bridge_state) as desired_state:
        # Need to set twice so the wired setting will be explicitly set,
        # allowing reapply to succeed.
        # https://bugzilla.redhat.com/1703960
        libnmstate.apply(desired_state)
        yield deepcopy(desired_state)


def test_create_and_remove_linux_bridge_with_min_desired_state():
    bridge_name = TEST_BRIDGE0
    with _linux_bridge(bridge_name, bridge_state=None) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_create_and_remove_linux_bridge_with_one_port(port0_up):
    bridge_name = TEST_BRIDGE0
    bridge_state = _create_bridge_subtree_config((TEST_BRIDGE0_PORT0,))
    with _linux_bridge(bridge_name, bridge_state) as desired_state:

        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_create_and_remove_linux_bridge_with_two_ports(port0_up, port1_up):
    bridge_name = TEST_BRIDGE0
    bridge_state = _create_bridge_subtree_config(
        (TEST_BRIDGE0_PORT0, TEST_BRIDGE0_PORT1)
    )

    with _linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


@ip_monitor_assert_stable_link_up(TEST_BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0):
    desired_state = bridge0_with_port0
    bridge_iface_state = desired_state[Interface.KEY][0]
    bridge_state = bridge_iface_state[LinuxBridge.CONFIG_SUBTREE]
    _add_port_to_bridge(bridge_state, 'eth2')

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_linux_bridge_uses_the_port_mac(port0_up, bridge0_with_port0):
    prev_port_mac = port0_up[Interface.KEY][0][Interface.MAC]
    current_state = show_only((TEST_BRIDGE0, TEST_BRIDGE0_PORT0))
    curr_iface0_mac = current_state[Interface.KEY][0][Interface.MAC]
    curr_iface1_mac = current_state[Interface.KEY][1][Interface.MAC]

    assert prev_port_mac == curr_iface0_mac == curr_iface1_mac


def _add_port_to_bridge(bridge_state, ifname):
    port_state = yaml.load(BRIDGE_PORT_YAML, Loader=yaml.SafeLoader)
    port_state[LinuxBridge.PORT_NAME] = ifname
    bridge_state[LinuxBridge.PORT_SUBTREE] += [port_state]


def _create_bridge_subtree_config(port_names):
    bridge_state = yaml.load(BRIDGE_OPTIONS_YAML, Loader=yaml.SafeLoader)

    ports_state = []
    for port in port_names:
        port_state = yaml.load(BRIDGE_PORT_YAML, Loader=yaml.SafeLoader)
        port_state[LinuxBridge.PORT_NAME] = port
        ports_state.append(port_state)

    bridge_state[LinuxBridge.PORT_SUBTREE] = ports_state
    return bridge_state


@contextmanager
def _linux_bridge(name, bridge_state):
    desired_state = {
        INTERFACES: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    if bridge_state:
        desired_state[INTERFACES][0][LinuxBridge.CONFIG_SUBTREE] = bridge_state

    libnmstate.apply(desired_state)

    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                INTERFACES: [
                    {
                        Interface.NAME: name,
                        Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )
