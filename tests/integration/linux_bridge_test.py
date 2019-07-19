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
from .testlib.assertlib import assert_mac_address

TEST_BRIDGE0 = 'linux-br0'


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
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
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
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    with _linux_bridge(bridge_name, bridge_state) as desired_state:

        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_create_and_remove_linux_bridge_with_two_ports(port0_up, port1_up):
    bridge_name = TEST_BRIDGE0
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port0_name, port1_name))

    with _linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_remove_bridge_and_keep_slave_up(bridge0_with_port0, port0_up):
    bridge_name = bridge0_with_port0[Interface.KEY][0][Interface.NAME]
    port_name = port0_up[Interface.KEY][0][Interface.NAME]

    port_desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: port_name,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {'enabled': False},
                Interface.IPV6: {'enabled': False},
            }
        ]
    }
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: bridge_name,
                Interface.STATE: InterfaceState.ABSENT,
            },
            port_desired_state[Interface.KEY][0],
        ]
    }

    libnmstate.apply(desired_state)

    current_state = show_only((bridge_name, port_name))

    assertlib.assert_state_match(port_desired_state)
    assert 1 == len(current_state[Interface.KEY])


@ip_monitor_assert_stable_link_up(TEST_BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up):
    desired_state = bridge0_with_port0
    bridge_iface_state = desired_state[Interface.KEY][0]
    bridge_state = bridge_iface_state[LinuxBridge.CONFIG_SUBTREE]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    _add_port_to_bridge(bridge_state, port1_name)

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_linux_bridge_uses_the_port_mac(port0_up, bridge0_with_port0):
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    current_state = show_only((TEST_BRIDGE0, port0_name))
    assert_mac_address(
        current_state, port0_up[Interface.KEY][0][Interface.MAC]
    )


def test_add_linux_bridge_with_empty_ipv6_static_address(port0_up):
    bridge_name = TEST_BRIDGE0
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    # Disable STP to avoid topology changes and the consequence link change.
    options_subtree = bridge_state[LinuxBridge.OPTIONS_SUBTREE]
    options_subtree[LinuxBridge.STP_SUBTREE][LinuxBridge.STP_ENABLED] = False

    extra_iface_state = {
        Interface.IPV6: {'enabled': True, 'autoconf': False, 'dhcp': False}
    }
    with _linux_bridge(
        bridge_name, bridge_state, extra_iface_state
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_linux_bridge_add_port_with_name_only(bridge0_with_port0, port1_up):
    desired_state = bridge0_with_port0
    bridge_iface_state = desired_state[Interface.KEY][0]
    bridge_state = bridge_iface_state[LinuxBridge.CONFIG_SUBTREE]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_state[LinuxBridge.PORT_SUBTREE].append(
        {LinuxBridge.PORT_NAME: port1_name}
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state_match(desired_state)


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
def _linux_bridge(name, bridge_state, extra_iface_state=None):
    desired_state = {
        INTERFACES: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    if extra_iface_state:
        desired_state[INTERFACES][0].update(extra_iface_state)

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
