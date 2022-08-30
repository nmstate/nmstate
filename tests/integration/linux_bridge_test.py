#
# Copyright (c) 2019-2021 Red Hat, Inc.
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
import os
import time

import pytest
import yaml
import json

import libnmstate
from libnmstate.error import NmstateKernelIntegerRoundedError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.prettystate import PrettyState
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge
from libnmstate.schema import VLAN

from .testlib import assertlib
from .testlib.assertlib import assert_mac_address
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import generate_vlan_filtering_config
from .testlib.bridgelib import generate_vlan_id_config
from .testlib.bridgelib import generate_vlan_id_range_config
from .testlib.bridgelib import linux_bridge
from .testlib.cmdlib import exec_cmd
from .testlib.env import is_fedora
from .testlib.env import is_ubuntu_kernel
from .testlib.env import nm_major_minor_version
from .testlib.ifacelib import get_mac_address
from .testlib.iproutelib import ip_monitor_assert_stable_link_up
from .testlib.retry import retry_till_true_or_timeout
from .testlib.statelib import show_only
from .testlib.vlan import vlan_interface


TEST_BRIDGE0 = "linux-br0"
TEST_TAP0 = "test-tap0"
TEST_BOND0 = "test-bond0"
ETH1 = "eth1"
# RFC 7042 reserved EUI-48 MAC range for document
TEST_MAC_ADDRESS = "00:00:5E:00:53:01"
VERIFY_RETRY_TMO = 5

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

VLAN_FILTER_PORT_YAML = """
    port:
    - name: eth1
      stp-hairpin-mode: false
      stp-path-cost: 100
      stp-priority: 32
      vlan:
        enable-native: true
        mode: trunk
        tag: 300
        trunk-tags:
        - id-range:
            max: 102
            min: 100
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


def _vlan_filtering_enabled(bridge_name):
    _, npc_output, _ = exec_cmd(
        cmd=(
            "npc",
            "iface",
            bridge_name,
        ),
        check=True,
    )
    return "vlan_filtering: true" in npc_output


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


@pytest.mark.tier1
def test_create_and_remove_linux_bridge_with_two_ports(port0_up, port1_up):
    bridge_name = TEST_BRIDGE0
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port0_name, port1_name))

    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)


@pytest.mark.tier1
def test_remove_bridge_and_keep_port_up(bridge0_with_port0, port0_up):
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


@pytest.mark.tier1
def test_create_vlan_as_port_of_linux_bridge(port0_vlan101):
    bridge_name = TEST_BRIDGE0
    port_name = port0_vlan101[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port_name,))
    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_create_vlan_over_linux_bridge(bridge0_with_port0):
    vlan_base_iface = TEST_BRIDGE0
    vlan_id = 101
    port_name = "{}.{}".format(vlan_base_iface, vlan_id)
    with vlan_interface(port_name, vlan_id, vlan_base_iface) as desired_state:
        assertlib.assert_state(desired_state)


@pytest.mark.tier1
@ip_monitor_assert_stable_link_up(TEST_BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up):
    desired_state = bridge0_with_port0
    bridge_iface_state = desired_state[Interface.KEY][0]
    bridge_state = bridge_iface_state[LinuxBridge.CONFIG_SUBTREE]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    _add_port_to_bridge(bridge_state, port1_name)

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
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
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    current_state = show_only((TEST_BRIDGE0, port0_name))
    assert_mac_address(
        current_state, port0_up[Interface.KEY][0][Interface.MAC]
    )


@pytest.mark.tier1
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


@pytest.mark.tier1
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


def test_linux_bridge_over_bond_over_port_in_one_transaction(bond0):
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
    with pytest.raises((NmstateVerificationError, NmstateValueError)):
        with linux_bridge(bridge_name, bridge_state) as desired_state:
            desired_state[Interface.KEY][0]["invalid_key"] = "foo"
            libnmstate.apply(desired_state)

    time.sleep(5)  # Give some time for NetworkManager to rollback
    current_state = libnmstate.show()
    assert original_state == current_state


@pytest.mark.tier1
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


class TestVlanFiltering:
    ACCESS_TAG = 300

    @pytest.fixture
    def bridge_with_trunk_port_and_native_config(self, port0_up):
        trunk_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.TRUNK,
            native_vlan=True,
            tag=TestVlanFiltering.ACCESS_TAG,
            trunk_tags=generate_vlan_id_config(100, 101, 102),
        )
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(trunk_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as state:
            yield state

    @pytest.fixture
    def bridge_with_access_port_config(self, port0_up):
        access_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.ACCESS,
            tag=TestVlanFiltering.ACCESS_TAG,
        )
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(access_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as state:
            yield state

    @pytest.mark.parametrize(
        "is_native_vlan", [True, False], ids=["native", "not-native"]
    )
    def test_trunk_port_config(self, is_native_vlan, port0_up):
        trunk_tags = generate_vlan_id_config(100, 101)
        trunk_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.TRUNK,
            tag=TestVlanFiltering.ACCESS_TAG if is_native_vlan else None,
            trunk_tags=trunk_tags,
            native_vlan=is_native_vlan,
        )

        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(trunk_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    @pytest.mark.parametrize(
        "is_native_vlan", [True, False], ids=["native", "not-native"]
    )
    def test_port_with_multiple_trunk_ports_config(
        self, is_native_vlan, port0_up
    ):
        trunk_tags = generate_vlan_id_config(100, 102)
        trunk_tags.append(generate_vlan_id_range_config(200, 299))
        trunk_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.TRUNK,
            tag=TestVlanFiltering.ACCESS_TAG if is_native_vlan else None,
            trunk_tags=trunk_tags,
            native_vlan=is_native_vlan,
        )

        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(trunk_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_access_port_config(self, port0_up):
        access_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.ACCESS, tag=TestVlanFiltering.ACCESS_TAG
        )
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(access_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_update_trunk_port_to_access_port(
        self, bridge_with_trunk_port_and_native_config, port0_up
    ):
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))

        new_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.ACCESS,
            tag=TestVlanFiltering.ACCESS_TAG + 5,
        )
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(new_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_update_trunk_port_tag_ids(
        self, bridge_with_trunk_port_and_native_config, port0_up
    ):
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))

        new_trunk_tags = generate_vlan_id_config(600, 602)
        new_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.TRUNK, trunk_tags=new_trunk_tags
        )
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(new_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_update_access_port_tag_id(
        self, bridge_with_access_port_config, port0_up
    ):
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))

        new_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.ACCESS,
            tag=TestVlanFiltering.ACCESS_TAG * 2,
        )
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(new_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_activate_vlan_filtering_on_bridge(
        self, bridge0_with_port0, port0_up
    ):
        port_name = port0_up[Interface.KEY][0][Interface.NAME]
        bridge_state = _create_bridge_subtree_config((port_name,))

        new_trunk_tags = generate_vlan_id_config(600, 602)
        new_port_state = generate_vlan_filtering_config(
            LinuxBridge.Port.Vlan.Mode.TRUNK, trunk_tags=new_trunk_tags
        )
        bridge_state[LinuxBridge.PORT_SUBTREE][0].update(new_port_state)
        with linux_bridge(TEST_BRIDGE0, bridge_state) as desired_state:
            assertlib.assert_state_match(desired_state)
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_disable_vlan_filtering_on_bridge(
        self,
        bridge_with_trunk_port_and_native_config,
    ):
        bridge_state = bridge_with_trunk_port_and_native_config[Interface.KEY][
            0
        ]
        bridge_config_subtree = bridge_state[LinuxBridge.CONFIG_SUBTREE]
        bridge_ports = bridge_config_subtree[LinuxBridge.PORT_SUBTREE]
        bridge_ports[0].update({LinuxBridge.Port.VLAN_SUBTREE: {}})

        with linux_bridge(
            TEST_BRIDGE0, bridge_config_subtree
        ) as desired_state:
            assertlib.assert_state(desired_state)
            assert not _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_keep_vlan_filtering_on_bridge_when_not_set(
        self,
        bridge_with_trunk_port_and_native_config,
    ):
        bridge_state = bridge_with_trunk_port_and_native_config[Interface.KEY][
            0
        ]
        bridge_config_subtree = bridge_state[LinuxBridge.CONFIG_SUBTREE]
        bridge_ports = bridge_config_subtree[LinuxBridge.PORT_SUBTREE]
        bridge_ports[0].pop(LinuxBridge.Port.VLAN_SUBTREE, {})

        with linux_bridge(TEST_BRIDGE0, bridge_config_subtree):
            assert _vlan_filtering_enabled(TEST_BRIDGE0)

    def test_pretty_state_port_name_first(
        self, bridge_with_trunk_port_and_native_config
    ):
        current_state = show_only((TEST_BRIDGE0,))
        pretty_state = PrettyState(current_state)
        assert VLAN_FILTER_PORT_YAML in pretty_state.yaml

    def test_move_bridge_port_to_bond(self, bridge_with_access_port_config):
        with bond_interface(
            TEST_BOND0, ["eth1"], create=False
        ) as desired_state:
            desired_state[Interface.KEY].append(
                {
                    Interface.NAME: TEST_BRIDGE0,
                    LinuxBridge.CONFIG_SUBTREE: {LinuxBridge.PORT_SUBTREE: []},
                }
            )
            libnmstate.apply(desired_state)


@pytest.fixture
def bridge_unmanaged_port():
    bridge_config = _create_bridge_subtree_config([])
    with linux_bridge(TEST_BRIDGE0, bridge_config):
        with dummy0_as_port(TEST_BRIDGE0):
            current_state = show_only((TEST_BRIDGE0,))
            yield current_state


def test_bridge_with_unmanaged_ports(bridge_unmanaged_port):
    bridge_state = bridge_unmanaged_port[Interface.KEY][0]
    port_subtree = bridge_state[LinuxBridge.CONFIG_SUBTREE][
        LinuxBridge.PORT_SUBTREE
    ]

    assert port_subtree[0][LinuxBridge.Port.NAME] == "dummy0"


@contextmanager
def dummy0_as_port(controller):
    exec_cmd(("ip", "link", "add", "dummy0", "type", "dummy"), check=True)
    try:
        exec_cmd(("ip", "link", "set", "dummy0", "up"), check=True)
        exec_cmd(
            ("nmcli", "dev", "set", "dummy0", "managed", "no"), check=True
        )
        exec_cmd(
            ("ip", "link", "set", "dummy0", "master", controller), check=True
        )
        yield
    finally:
        exec_cmd(("ip", "link", "delete", "dummy0"))
        exec_cmd(("nmcli", "c", "del", "dummy0"))


def test_add_invalid_port_ip_config(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.ENABLED] = True
    desired_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.DHCP] = True
    bridge_state = _create_bridge_subtree_config(("eth1",))
    with pytest.raises(NmstateValueError):
        with linux_bridge(
            TEST_BRIDGE0, bridge_state, create=False
        ) as lb_state:
            desired_state[Interface.KEY].append(lb_state[Interface.KEY][0])
            libnmstate.apply(desired_state)


def _add_port_to_bridge(bridge_state, ifname):
    port_state = yaml.load(BRIDGE_PORT_YAML, Loader=yaml.SafeLoader)
    add_port_to_bridge(bridge_state, ifname, port_state)


def _create_bridge_subtree_config(port_names):
    bridge_state = yaml.load(BRIDGE_OPTIONS_YAML, Loader=yaml.SafeLoader)

    for port in port_names:
        port_state = yaml.load(BRIDGE_PORT_YAML, Loader=yaml.SafeLoader)
        add_port_to_bridge(bridge_state, port, port_state)

    return bridge_state


@pytest.mark.tier1
def test_change_linux_bridge_group_addr(bridge0_with_port0):
    iface_state = bridge0_with_port0[Interface.KEY][0]
    iface_state[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.OPTIONS_SUBTREE][
        LinuxBridge.Options.GROUP_ADDR
    ] = "01:80:C2:00:00:04"

    desired_state = {Interface.KEY: [iface_state]}

    libnmstate.apply(desired_state)

    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not is_ubuntu_kernel(),
    reason="Only 250 HZ kernel will fail on NmstateKernelIntergerRounded "
    "for linux bridge MULTICAST_STARTUP_QUERY_INTERVAL option",
)
def test_linux_bridge_option_integer_rounded_on_ubuntu_kernel(
    bridge0_with_port0,
):
    iface_state = bridge0_with_port0[Interface.KEY][0]
    iface_state[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.OPTIONS_SUBTREE][
        LinuxBridge.Options.MULTICAST_STARTUP_QUERY_INTERVAL
    ] = 3125

    desired_state = {Interface.KEY: [iface_state]}

    with pytest.raises(NmstateKernelIntegerRoundedError):
        libnmstate.apply(desired_state)


@pytest.mark.tier1
def test_moving_ports_from_absent_interface(bridge0_with_port0):
    iface_state = bridge0_with_port0[Interface.KEY][0]
    iface_state[Interface.NAME] = "linux-br1"

    libnmstate.apply(
        {
            Interface.KEY: [
                iface_state,
                {
                    Interface.NAME: TEST_BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )

    assertlib.assert_state_match({Interface.KEY: [iface_state]})
    assertlib.assert_absent(TEST_BRIDGE0)

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "linux-br1",
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


def test_linux_bridge_replace_unmanaged_port(bridge_unmanaged_port, eth1_up):
    iface_state = bridge_unmanaged_port[Interface.KEY][0]
    iface_state.pop(Interface.MAC)
    iface_state[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE] = [
        {LinuxBridge.Port.NAME: "eth1"}
    ]
    libnmstate.apply({Interface.KEY: [iface_state]})


@pytest.fixture
def bridge0_with_tap_port():
    exec_cmd(f"ip tuntap add name {TEST_TAP0} mode tap".split(), check=True)
    exec_cmd(f"ip link add {TEST_BRIDGE0} type bridge".split(), check=True)
    exec_cmd(
        f"ip link set {TEST_TAP0} master {TEST_BRIDGE0}".split(), check=True
    )
    exec_cmd(f"ip link set {TEST_TAP0} up".split(), check=True)
    exec_cmd(f"ip link set {TEST_BRIDGE0} up".split(), check=True)
    yield
    exec_cmd(f"ip link del {TEST_TAP0}".split())
    exec_cmd(f"ip link del {TEST_BRIDGE0}".split())
    exec_cmd(f"nmcli c del {TEST_TAP0}".split())
    exec_cmd(f"nmcli c del {TEST_BRIDGE0}".split())


def test_ignore_unmanged_tap_as_bridge_port(bridge0_with_tap_port, port0_up):
    """
    The unknown interface should be still bridge port along with other ports
    """
    with _bridge0_with_port0(port0_up) as state:
        state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE][
            LinuxBridge.PORT_SUBTREE
        ].append({LinuxBridge.Port.NAME: TEST_TAP0})
        assertlib.assert_state_match(state)


def test_explicitly_ignore_a_bridge_port(bridge0_with_port0, port1_up):
    """
    The ignored interface should be still bridge port along with other ports
    """
    bridge_info = bridge0_with_port0[Interface.KEY][0]
    port0_name = bridge_info[LinuxBridge.CONFIG_SUBTREE][
        LinuxBridge.PORT_SUBTREE
    ][0][LinuxBridge.Port.NAME]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    _add_port_to_bridge(bridge_info[LinuxBridge.CONFIG_SUBTREE], port1_name)
    desired_state = {
        Interface.KEY: [
            bridge_info,
            {
                Interface.NAME: port0_name,
                Interface.STATE: InterfaceState.IGNORE,
            },
        ]
    }
    print(desired_state)
    libnmstate.apply(desired_state)
    state = show_only((TEST_BRIDGE0,))
    cur_port_config = state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE][
        LinuxBridge.PORT_SUBTREE
    ]
    assert cur_port_config[0][LinuxBridge.Port.NAME] == port0_name
    assert cur_port_config[1][LinuxBridge.Port.NAME] == port1_name


@pytest.mark.xfail(
    reason="https://bugzilla.redhat.com/1855160",
    raises=NmstateVerificationError,
)
def test_change_multicast_snooping_from_false_to_true(port0_up, port1_up):
    bridge_name = TEST_BRIDGE0
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    port1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_state = _create_bridge_subtree_config((port0_name, port1_name))
    bridge_state[LinuxBridge.OPTIONS_SUBTREE][
        LinuxBridge.Options.MULTICAST_SNOOPING
    ] = False
    with linux_bridge(bridge_name, bridge_state, create=True) as lb_state:
        bridge = lb_state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE]
        bridge[LinuxBridge.OPTIONS_SUBTREE][
            LinuxBridge.Options.MULTICAST_SNOOPING
        ] = True
        libnmstate.apply(lb_state)


def test_empty_state_does_not_change_bridge_options(bridge0_with_port0):
    original_state = show_only((TEST_BRIDGE0,))
    libnmstate.apply({Interface.KEY: [{Interface.NAME: TEST_BRIDGE0}]})
    assertlib.assert_state_match(original_state)


def test_create_bridge_with_mixed_case_group_addr():
    bridge_state = _create_bridge_subtree_config([])

    bridge_state[LinuxBridge.OPTIONS_SUBTREE][
        LinuxBridge.Options.GROUP_ADDR
    ] = "01:80:C2:00:00:0a"
    print(bridge_state)
    with linux_bridge(TEST_BRIDGE0, bridge_state) as lb_state:
        assertlib.assert_state_match(lb_state)


@pytest.mark.tier1
def test_create_linux_bridge_with_copy_mac_from(eth1_up, eth2_up):
    eth2_mac = eth2_up[Interface.KEY][0][Interface.MAC]
    bridge_state = _create_bridge_subtree_config(["eth1", "eth2"])

    with linux_bridge(
        TEST_BRIDGE0,
        bridge_state,
        extra_iface_state={Interface.COPY_MAC_FROM: "eth2"},
    ):
        current_state = show_only((TEST_BRIDGE0,))
        assert_mac_address(current_state, eth2_mac)


def _get_permanent_mac(iface_name):
    np_iface = json.loads(
        exec_cmd(f"npc iface {iface_name} --json".split())[1]
    )
    return np_iface[0].get("permanent_mac_address")


@pytest.fixture
def real_nic_with_mac_differ_from_permanent():
    test_nic = os.environ.get("TEST_REAL_NIC")
    permanent_mac = _get_permanent_mac(test_nic)
    assert permanent_mac
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: test_nic,
                    Interface.MAC: TEST_MAC_ADDRESS,
                }
            ]
        }
    )
    yield permanent_mac
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: test_nic,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_create_linux_bridge_with_copy_mac_from_permanent_mac(
    real_nic_with_mac_differ_from_permanent,
):
    permanent_mac = real_nic_with_mac_differ_from_permanent
    test_nic = os.environ.get("TEST_REAL_NIC")

    # Create bridge use this nic
    bridge_state = _create_bridge_subtree_config([test_nic])
    with linux_bridge(
        TEST_BRIDGE0,
        bridge_state,
        extra_iface_state={Interface.COPY_MAC_FROM: test_nic},
    ):
        current_state = show_only((TEST_BRIDGE0,))
        assert_mac_address(current_state, permanent_mac)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_major_minor_version() < 1.31,
    reason="Modifying accept-all-mac-addresses is not supported on NM.",
)
def test_linux_bridge_enable_and_disable_accept_all_mac_addresses(
    bridge0_with_port0,
):
    desired_state = bridge0_with_port0
    desired_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = True
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    desired_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = False
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_desire_port_only_should_preserve_ctrl_setting(bridge0_with_port0):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                }
            ]
        }
    )

    def _is_bridge_still_have_port():
        state = show_only((TEST_BRIDGE0,))
        ports = state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE][
            LinuxBridge.PORT_SUBTREE
        ]
        return len(ports) == 1 and ports[0][LinuxBridge.Port.NAME] == "eth1"

    assert retry_till_true_or_timeout(
        VERIFY_RETRY_TMO, _is_bridge_still_have_port
    )


@pytest.mark.tier1
@pytest.mark.parametrize(
    "mcast_router_value",
    [
        0,
        2,
        1,
        "disabled",
        "enabled",
        "auto",
    ],
    ids=[
        "disabled_integer",
        "enabled_integer",
        "auto_integer",
        "disabled",
        "enabled",
        "auto",
    ],
)
def test_linux_bridge_multicast_router(bridge0_with_port0, mcast_router_value):
    iface_state = {
        Interface.NAME: TEST_BRIDGE0,
        LinuxBridge.CONFIG_SUBTREE: {
            LinuxBridge.OPTIONS_SUBTREE: {
                LinuxBridge.Options.MULTICAST_ROUTER: mcast_router_value,
            }
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})


@pytest.mark.tier1
def test_linux_bridge_show_port_ip_as_disabled(bridge0_with_port0):
    state = show_only(("eth1",))

    assert state[Interface.KEY][0][Interface.IPV4] == {
        InterfaceIPv4.ENABLED: False
    }
    assert state[Interface.KEY][0][Interface.IPV6] == {
        InterfaceIPv6.ENABLED: False
    }


@pytest.mark.tier1
@pytest.mark.parametrize(
    "vlan_protocol",
    [
        VLAN.PROTOCOL_802_1AD,
        VLAN.PROTOCOL_802_1Q,
    ],
)
def test_linux_bridge_set_vlan_protocol(bridge0_with_port0, vlan_protocol):
    iface_state = {
        Interface.NAME: TEST_BRIDGE0,
        LinuxBridge.CONFIG_SUBTREE: {
            LinuxBridge.OPTIONS_SUBTREE: {
                LinuxBridge.Options.VLAN_PROTOCOL: vlan_protocol,
            }
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})


def test_create_and_remove_linux_bridge_kernel_mode():
    bridge_name = TEST_BRIDGE0
    with linux_bridge(
        bridge_name,
        bridge_subtree_state=None,
        kernel_mode=True,
        create=False,
    ) as desired_state:
        desired_state[Interface.KEY][0].pop(Interface.IPV4)
        desired_state[Interface.KEY][0].pop(Interface.IPV6)
        libnmstate.apply(desired_state, kernel_only=True)
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(bridge_name)
