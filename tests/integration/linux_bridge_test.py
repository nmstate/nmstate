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

import yaml

from libnmstate import netapplier
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge

from .testlib import assertlib
from .testlib.statelib import INTERFACES


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

BRIDGE_PORT_ETH1_YAML = """
port:
  - name: eth1
    stp-hairpin-mode: false
    stp-path-cost: 100
    stp-priority: 32
"""


def test_create_and_remove_linux_bridge_with_one_port(eth1_up):
    bridge_name = 'linux-br0'
    bridge_state = yaml.load(BRIDGE_OPTIONS_YAML)
    port_state = yaml.load(BRIDGE_PORT_ETH1_YAML)
    bridge_state.update(port_state)

    with linux_bridge(bridge_name, bridge_state) as desired_state:

        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_create_and_remove_linux_bridge_with_min_desired_state():
    bridge_name = 'linux-br0'
    with linux_bridge(bridge_name, bridge_state=None) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


@contextmanager
def linux_bridge(name, bridge_state):
    desired_state = {
        INTERFACES: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                Interface.STATE: InterfaceState.UP
            }
        ]
    }
    if bridge_state:
        desired_state[INTERFACES][0][LinuxBridge.CONFIG_SUBTREE] = bridge_state

    netapplier.apply(desired_state)

    try:
        yield desired_state
    finally:
        netapplier.apply({
            INTERFACES: [
                {
                    Interface.NAME: name,
                    Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                    Interface.STATE: InterfaceState.ABSENT
                }
            ]
        })


def test_create_and_remove_linux_bridge_with_two_ports(eth1_up, eth2_up):
    bridge_name = 'linux-br0'
    bridge_state = yaml.load(BRIDGE_OPTIONS_YAML)
    port1_state = yaml.load(BRIDGE_PORT_ETH1_YAML)
    port2_state = yaml.load(BRIDGE_PORT_ETH1_YAML)
    port2_state[LinuxBridge.PORT_SUBTREE][0][LinuxBridge.PORT_NAME] = 'eth2'
    bridge_state.update(port1_state)
    bridge_state[LinuxBridge.PORT_SUBTREE].append(
        port2_state[LinuxBridge.PORT_SUBTREE][0])

    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)
