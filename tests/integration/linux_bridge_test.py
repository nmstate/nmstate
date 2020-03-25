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
from copy import deepcopy

import time
import pytest
import yaml

import libnmstate
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge

from .testlib import assertlib
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import linux_bridge
from .testlib.cmdlib import exec_cmd
from .testlib.ifacelib import get_mac_address
from .testlib.iproutelib import ip_monitor_assert_stable_link_up
from .testlib.statelib import show_only
from .testlib.assertlib import assert_mac_address
from .testlib.vlan import vlan_interface
from .testlib.env import is_fedora


TEST_BRIDGE0 = "linux-br0"


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
    with _bridge0_with_port0(port0_up) as state:
        yield state


@pytest.fixture
def bridge0_with_port0_with_explicit_port_mac(port0_up):
    with _bridge0_with_port0(port0_up, use_port_mac=True) as state:
        yield state


@contextmanager
def _bridge0_with_port0(port0_up, use_port_mac=False):
    bridge_name = TEST_BRIDGE0
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    # Disable STP to avoid topology changes and the consequence link change.
    options_subtree = bridge_state[LinuxBridge.OPTIONS_SUBTREE]
    options_subtree[LinuxBridge.STP_SUBTREE][LinuxBridge.STP.ENABLED] = False

    extra_iface_state = None

    if use_port_mac:
        extra_iface_state = {Interface.MAC: get_mac_address(port_name)}

    with linux_bridge(
        bridge_name, bridge_state, extra_iface_state
    ) as desired_state:
        yield deepcopy(desired_state)


@pytest.fixture
def port0_vlan101(port0_up):
    vlan_id = 101
    vlan_base_iface = port0_up[Interface.KEY][0][Interface.NAME]
    port_name = "{}.{}".format(vlan_base_iface, vlan_id)
    with vlan_interface(port_name, vlan_id, vlan_base_iface):
        state = show_only((port_name,))
        yield state


@pytest.fixture
def bond0(port0_up):
    bond_name = "testbond0"
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(bond_name, [port_name], create=False) as bond0:
        yield bond0


def test_create_and_remove_linux_bridge_with_min_desired_state():
    bridge_name = TEST_BRIDGE0
    with linux_bridge(bridge_name, bridge_subtree_state=None) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_create_and_remove_linux_bridge_with_one_port(port0_up):
    bridge_name = TEST_BRIDGE0
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    with linux_bridge(bridge_name, bridge_state) as desired_state:

        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)

    state = show_only((port_name,))
    assert state
    assert state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP


def test_create_and_remove_linux_bridge_with_two_ports(port0_up, port1_up):
    bridge_name = TEST_BRIDGE0
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port0_name, port1_name))

    with linux_bridge(bridge_name, bridge_state) as desired_state:
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
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
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


def test_create_vlan_as_slave_of_linux_bridge(port0_vlan101):
    bridge_name = TEST_BRIDGE0
    port_name = port0_vlan101[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state(desired_state)


def test_create_vlan_over_linux_bridge(bridge0_with_port0):
    vlan_base_iface = TEST_BRIDGE0
    vlan_id = 101
    port_name = "{}.{}".format(vlan_base_iface, vlan_id)
    with vlan_interface(port_name, vlan_id, vlan_base_iface) as desired_state:
        assertlib.assert_state(desired_state)


@ip_monitor_assert_stable_link_up(TEST_BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up):
    desired_state = bridge0_with_port0
    bridge_iface_state = desired_state[Interface.KEY][0]
    bridge_state = bridge_iface_state[LinuxBridge.CONFIG_SUBTREE]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    _add_port_to_bridge(bridge_state, port1_name)

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.xfail(
    is_fedora(),
    reason=(
        "On Fedora 31+, users need to explicitly configure the port MAC "
        "due to changes to the default systemd config."
    ),
    raises=AssertionError,
    strict=True,
)
def test_linux_bridge_uses_the_port_mac_implicitly(
    port0_up, bridge0_with_port0
):
    print(bridge0_with_port0)
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    current_state = show_only((TEST_BRIDGE0, port0_name))
    assert_mac_address(
        current_state, port0_up[Interface.KEY][0][Interface.MAC]
    )


def test_linux_bridge_uses_specified_mac_address(
    port0_up, bridge0_with_port0_with_explicit_port_mac
):
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
    options_subtree[LinuxBridge.STP_SUBTREE][LinuxBridge.STP.ENABLED] = False

    extra_iface_state = {
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.AUTOCONF: False,
            InterfaceIPv6.DHCP: False,
        }
    }
    with linux_bridge(
        bridge_name, bridge_state, extra_iface_state
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


def test_add_linux_bridge_with_empty_ipv6_static_address_with_stp(port0_up):
    bridge_name = TEST_BRIDGE0
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    options_subtree = bridge_state[LinuxBridge.OPTIONS_SUBTREE]
    options_subtree[LinuxBridge.STP_SUBTREE][LinuxBridge.STP.ENABLED] = True

    extra_iface_state = {
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.AUTOCONF: False,
            InterfaceIPv6.DHCP: False,
        }
    }
    with linux_bridge(
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
        {LinuxBridge.Port.NAME: port1_name}
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state_match(desired_state)


def test_replace_port_on_linux_bridge(port0_vlan101, port1_up):
    bridge_name = TEST_BRIDGE0
    vlan_port0_name = port0_vlan101[Interface.KEY][0][Interface.NAME]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((vlan_port0_name,))
    with linux_bridge(bridge_name, bridge_state) as state:
        brconf_state = state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE]
        brconf_state[LinuxBridge.PORT_SUBTREE] = [
            {LinuxBridge.Port.NAME: port1_name}
        ]
        libnmstate.apply(state)

        br_state = show_only((bridge_name,))
        brconf_state = br_state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE]
        br_ports_state = brconf_state[LinuxBridge.PORT_SUBTREE]
        assert 1 == len(br_ports_state)
        assert port1_name == br_ports_state[0][LinuxBridge.Port.NAME]

        port_state = show_only((vlan_port0_name,))
        assert (
            InterfaceState.UP == port_state[Interface.KEY][0][Interface.STATE]
        )


def test_linux_bridge_over_bond_over_slave_in_one_transaction(bond0):
    bridge_name = TEST_BRIDGE0
    bond_name = bond0[Interface.KEY][0][Interface.NAME]
    bridge_config_state = _create_bridge_subtree_config((bond_name,))
    with linux_bridge(
        bridge_name, bridge_config_state, create=False
    ) as bridge0:
        desired_state = bond0
        bridge_state = bridge0[Interface.KEY][0]
        desired_state[Interface.KEY].append(bridge_state)
        libnmstate.apply(desired_state)

        assertlib.assert_state_match(desired_state)

    assertlib.assert_absent(bridge_name)


def test_rollback_for_linux_bridge():
    original_state = libnmstate.show()
    bridge_name = TEST_BRIDGE0
    bridge_state = _create_bridge_subtree_config(())
    with pytest.raises(NmstateVerificationError):
        with linux_bridge(bridge_name, bridge_state) as desired_state:
            desired_state[Interface.KEY][0]["invalid_key"] = "foo"
            libnmstate.apply(desired_state)

    time.sleep(5)  # Give some time for NetworkManager to rollback
    current_state = libnmstate.show()
    assert original_state == current_state


def test_activate_empty_bridge_does_not_blocked_by_dhcp():
    bridge_name = TEST_BRIDGE0
    bridge_state = None
    extra_iface_state = {
        Interface.IPV4: {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: True,
        },
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.AUTOCONF: True,
            InterfaceIPv6.DHCP: True,
        },
    }
    with linux_bridge(
        bridge_name, bridge_state, extra_iface_state
    ) as desired_state:
        assertlib.assert_state(desired_state)


@pytest.mark.xfail(
    raises=NmstateNotImplementedError,
    reason="https://nmstate.atlassian.net/browse/NMSTATE-230",
    strict=True,
)
def test_port_vlan_not_implemented(port0_up):
    bridge_name = TEST_BRIDGE0
    port_name = port0_up[Interface.KEY][0][Interface.NAME]
    port_vlan_config = {
        LinuxBridge.Port.VLAN_SUBTREE: {
            LinuxBridge.Port.Vlan.MODE: LinuxBridge.Port.Vlan.Mode.ACCESS,
            LinuxBridge.Port.Vlan.TAG: 101,
        }
    }

    bridge_state = _create_bridge_subtree_config((port_name,))
    bridge_state[LinuxBridge.PORT_SUBTREE][0].update(port_vlan_config)
    with linux_bridge(bridge_name, bridge_state):
        pass


@pytest.fixture
def bridge_unmanaged_port():
    bridge_config = _create_bridge_subtree_config([])
    with linux_bridge(TEST_BRIDGE0, bridge_config):
        with dummy0_as_slave(TEST_BRIDGE0):
            current_state = show_only((TEST_BRIDGE0,))
            yield current_state


def test_bridge_with_unmanaged_ports(bridge_unmanaged_port):
    bridge_state = bridge_unmanaged_port[Interface.KEY][0]
    port_subtree = bridge_state[LinuxBridge.CONFIG_SUBTREE][
        LinuxBridge.PORT_SUBTREE
    ]

    assert port_subtree[0][LinuxBridge.Port.NAME] == "dummy0"


@contextmanager
def dummy0_as_slave(master):
    exec_cmd(("ip", "link", "add", "dummy0", "type", "dummy"), check=True)
    try:
        exec_cmd(("ip", "link", "set", "dummy0", "up"), check=True)
        exec_cmd(
            ("nmcli", "dev", "set", "dummy0", "managed", "no"), check=True
        )
        exec_cmd(("ip", "link", "set", "dummy0", "master", master), check=True)
        yield
    finally:
        exec_cmd(("ip", "link", "delete", "dummy0"))


def _add_port_to_bridge(bridge_state, ifname):
    port_state = yaml.load(BRIDGE_PORT_YAML, Loader=yaml.SafeLoader)
    add_port_to_bridge(bridge_state, ifname, port_state)


def _create_bridge_subtree_config(port_names):
    bridge_state = yaml.load(BRIDGE_OPTIONS_YAML, Loader=yaml.SafeLoader)

    for port in port_names:
        port_state = yaml.load(BRIDGE_PORT_YAML, Loader=yaml.SafeLoader)
        add_port_to_bridge(bridge_state, port, port_state)

    return bridge_state
