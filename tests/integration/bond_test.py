# SPDX-License-Identifier: LGPL-2.1-or-later

import os
import time

import pytest
import yaml

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateValueError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import VLAN

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import statelib
from .testlib.assertlib import assert_mac_address
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import create_bridge_subtree_state
from .testlib.bridgelib import linux_bridge
from .testlib.env import is_k8s
from .testlib.env import nm_minor_version
from .testlib.ifacelib import get_mac_address
from .testlib.ifacelib import ifaces_init
from .testlib.retry import retry_till_true_or_timeout
from .testlib.vlan import vlan_interface
from .testlib.yaml import load_yaml

BOND99 = "bond99"
ETH1 = "eth1"
ETH2 = "eth2"

IPV4_ADDRESS1 = "192.0.2.251"

MAC0 = "02:FF:FF:FF:FF:00"
MAC1 = "02:FF:FF:FF:FF:01"

TEST_VLAN_ID = 200
TEST_VLAN = f"{BOND99}.{TEST_VLAN_ID}"

BOND99_YAML_BASE = """
interfaces:
- name: bond99
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    port:
    - eth1
    - eth2
"""

BOND99_PORT_YAML_BASE = """
interfaces:
- name: bond99
  type: bond
  state: up
  link-aggregation:
    mode: active-backup
    ports-config:
    - name: eth1
      queue-id: 0
      priority: -1
    - name: eth2
      queue-id: 1
      priority: 2
"""

RETRY_TIMEOUT = 30


def iface_is_holding_expected_mac(iface_name, expected_mac):
    return get_mac_address(iface_name) == expected_mac


@pytest.fixture
def setup_remove_bond99():
    yield
    remove_bond = {
        Interface.KEY: [
            {
                Interface.NAME: BOND99,
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.ABSENT,
            }
        ]
    }
    libnmstate.apply(remove_bond)


@pytest.fixture
def bond99_with_2_port(eth1_up, eth2_up):
    port = [
        eth1_up[Interface.KEY][0][Interface.NAME],
        eth2_up[Interface.KEY][0][Interface.NAME],
    ]
    with bond_interface(BOND99, port) as state:
        yield state


@pytest.fixture
def bond88_with_port(eth1_up):
    port = [eth1_up[Interface.KEY][0][Interface.NAME]]
    with bond_interface(BOND99, port) as state:
        yield state


@pytest.fixture
def bond99_with_eth2(eth2_up):
    port = [eth2_up[Interface.KEY][0][Interface.NAME]]
    with bond_interface(BOND99, port) as state:
        yield state


@pytest.mark.tier1
def test_add_and_remove_bond_with_two_port(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE, Loader=yaml.SafeLoader)
    libnmstate.apply(state)

    assertlib.assert_state_match(state)

    state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT

    libnmstate.apply(state)

    state = statelib.show_only((state[Interface.KEY][0][Interface.NAME],))
    assert not state[Interface.KEY]

    state = statelib.show_only(
        (
            eth1_up[Interface.KEY][0][Interface.NAME],
            eth2_up[Interface.KEY][0][Interface.NAME],
        )
    )
    assert state
    assert state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
    assert state[Interface.KEY][1][Interface.STATE] == InterfaceState.UP


@pytest.mark.tier1
def test_remove_bond_with_minimum_desired_state(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE, Loader=yaml.SafeLoader)
    bond_name = state[Interface.KEY][0][Interface.NAME]

    libnmstate.apply(state)

    remove_bond_state = {
        Interface.KEY: [
            {
                Interface.NAME: bond_name,
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.ABSENT,
            }
        ]
    }
    libnmstate.apply(remove_bond_state)
    state = statelib.show_only((bond_name,))
    assert not state[Interface.KEY]


@pytest.mark.skipif(
    nm_minor_version() <= 44,
    reason="Bond port config is not supported on NetworkManager 1.44-",
)
def test_add_and_remove_bond_with_port_config(eth1_up, eth2_up):
    state = yaml.load(BOND99_PORT_YAML_BASE, Loader=yaml.SafeLoader)
    try:
        libnmstate.apply(state)
        assertlib.assert_state_match(state)
    finally:
        state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(state)


@pytest.mark.skipif(
    nm_minor_version() <= 44,
    reason="Bond port config is not supported on NetworkManager 1.44-",
)
def test_add_bond_with_port_config_and_modify(eth1_up, eth2_up):
    state = yaml.load(BOND99_PORT_YAML_BASE, Loader=yaml.SafeLoader)
    try:
        libnmstate.apply(state)
        assertlib.assert_state_match(state)
        bond_port_eth1 = {"name": "eth1", "priority": -1, "queue-id": 1}
        bond_port_eth2 = {"name": "eth2", "priority": 9, "queue-id": 0}
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
            Bond.PORTS_CONFIG_SUBTREE
        ][0] = bond_port_eth1
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
            Bond.PORTS_CONFIG_SUBTREE
        ][1] = bond_port_eth2
        libnmstate.apply(state)
        assertlib.assert_state_match(state)
    finally:
        state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(state)


@pytest.mark.skipif(
    nm_minor_version() <= 44,
    reason="Bond port config is not supported on NetworkManager 1.44-",
)
def test_conflict_port_name_between_port_and_ports_config(eth1_up, eth2_up):
    state = yaml.load(BOND99_PORT_YAML_BASE, Loader=yaml.SafeLoader)
    state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.PORT] = ["eth1"]
    with pytest.raises(NmstateValueError):
        libnmstate.apply(state)
    state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.PORT] = ["eth1", "eth3"]
    with pytest.raises(NmstateValueError):
        libnmstate.apply(state)


def test_add_bond_without_port():
    with bond_interface(name=BOND99, port=[]) as state:
        assert state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.PORT] == []


@pytest.mark.tier1
def test_add_bond_with_port_and_ipv4(eth1_up, eth2_up, setup_remove_bond99):
    desired_bond_state = {
        Interface.KEY: [
            {
                Interface.NAME: BOND99,
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: "192.168.122.250",
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.PORT: [
                        eth1_up[Interface.KEY][0][Interface.NAME],
                        eth2_up[Interface.KEY][0][Interface.NAME],
                    ],
                    Bond.OPTIONS_SUBTREE: {"miimon": "140"},
                },
            }
        ]
    }

    libnmstate.apply(desired_bond_state)

    assertlib.assert_state_match(desired_bond_state)


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=AssertionError,
    strict=False,
)
def test_rollback_for_bond(eth1_up, eth2_up):
    current_state = libnmstate.show()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BOND99,
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: "192.168.122.250",
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.PORT: [
                        eth1_up[Interface.KEY][0][Interface.NAME],
                        eth2_up[Interface.KEY][0][Interface.NAME],
                    ],
                    Bond.OPTIONS_SUBTREE: {"miimon": "140"},
                },
            }
        ]
    }

    desired_state[Interface.KEY][0]["invalid_key"] = "foo"

    with pytest.raises((NmstateVerificationError, NmstateValueError)):
        libnmstate.apply(desired_state)

    time.sleep(5)

    current_state_after_apply = libnmstate.show()
    assert (
        current_state[Interface.KEY]
        == current_state_after_apply[Interface.KEY]
    )


@pytest.mark.tier1
def test_add_port_to_bond_without_port(eth1_up):
    port_name = eth1_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, port=[]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.PORT] = [port_name]
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.PORT] == [port_name]


def test_remove_all_port_from_bond(bond99_with_2_port):
    state = bond99_with_2_port
    state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.PORT] = []

    libnmstate.apply(state)

    current_state = statelib.show_only((BOND99,))
    bond_cur_state = current_state[Interface.KEY][0]

    assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.PORT] == []


@pytest.mark.tier1
def test_replace_bond_port(eth1_up, eth2_up):
    port1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    port2_name = eth2_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, port=[port1_name]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.PORT] = [port2_name]

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.PORT] == [port2_name]


@pytest.mark.tier1
def test_remove_one_of_the_bond_port(eth1_up, eth2_up):
    port1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    port2_name = eth2_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, port=[port1_name, port2_name]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.PORT] = [port2_name]

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

    assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.PORT] == [port2_name]


@pytest.mark.tier1
def test_swap_port_between_bonds(bond88_with_port, bond99_with_eth2):
    bonding88 = bond88_with_port[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bonding99 = bond99_with_eth2[Interface.KEY][0][Bond.CONFIG_SUBTREE]

    bonding88[Bond.PORT], bonding99[Bond.PORT] = (
        bonding99[Bond.PORT],
        bonding88[Bond.PORT],
    )

    state = bond88_with_port
    state.update(bond99_with_eth2)
    libnmstate.apply(state)

    assertlib.assert_state_match(state)


@pytest.mark.tier1
def test_set_bond_mac_address(eth1_up):
    port_name = eth1_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, port=[port_name]) as state:
        state[Interface.KEY][0][Interface.MAC] = MAC0
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99, port_name))
        assert_mac_address(current_state, MAC0)

        state[Interface.KEY][0][Interface.MAC] = MAC1
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99, port_name))
        assert_mac_address(current_state, MAC1)


@pytest.mark.tier1
def test_changing_port_order_keeps_mac_of_existing_bond(bond99_with_2_port):
    bond_state = bond99_with_2_port[Interface.KEY][0]
    bond_port = bond_state[Bond.CONFIG_SUBTREE][Bond.PORT]
    ifaces_names = [bond_state[Interface.NAME]] + bond_port

    current_state = statelib.show_only(ifaces_names)
    assert_mac_address(current_state)

    bond_port.reverse()
    libnmstate.apply(bond99_with_2_port)

    modified_state = statelib.show_only(ifaces_names)
    assert_mac_address(
        modified_state, current_state[Interface.KEY][0][Interface.MAC]
    )


@pytest.mark.tier1
def test_adding_a_port_keeps_mac_of_existing_bond(bond99_with_eth2, eth1_up):
    desired_state = bond99_with_eth2
    bond_state = desired_state[Interface.KEY][0]
    bond_port = bond_state[Bond.CONFIG_SUBTREE][Bond.PORT]
    bond_port.insert(0, eth1_up[Interface.KEY][0][Interface.NAME])

    current_state = statelib.show_only((bond_state[Interface.NAME],))

    libnmstate.apply(desired_state)
    modified_state = statelib.show_only((bond_state[Interface.NAME],))
    assert (
        modified_state[Interface.KEY][0][Interface.MAC]
        == current_state[Interface.KEY][0][Interface.MAC]
    )


@pytest.mark.tier1
def test_adding_port_to_empty_bond_doesnt_keep_mac(eth1_up):
    with bond_interface(BOND99, []) as state:
        bond_state = state[Interface.KEY][0]
        eth1_name = eth1_up[Interface.KEY][0][Interface.NAME]
        bond_state[Bond.CONFIG_SUBTREE][Bond.PORT] = [eth1_name]

        current_state = statelib.show_only((bond_state[Interface.NAME],))

        libnmstate.apply(state)
        modified_state = statelib.show_only((bond_state[Interface.NAME],))
        assert (
            modified_state[Interface.KEY][0][Interface.MAC]
            != current_state[Interface.KEY][0][Interface.MAC]
        )


def test_removing_port_keeps_mac_of_existing_bond(bond99_with_2_port, eth1_up):
    desired_state = bond99_with_2_port
    bond_state = desired_state[Interface.KEY][0]
    eth1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    bond_state[Bond.CONFIG_SUBTREE][Bond.PORT] = [eth1_name]

    current_state = statelib.show_only((bond_state[Interface.NAME],))

    libnmstate.apply(desired_state)
    modified_state = statelib.show_only((bond_state[Interface.NAME],))
    assert (
        modified_state[Interface.KEY][0][Interface.MAC]
        == current_state[Interface.KEY][0][Interface.MAC]
    )


@pytest.mark.tier1
def test_bond_with_empty_ipv6_static_address(eth1_up):
    extra_iface_state = {
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.AUTOCONF: False,
            InterfaceIPv6.DHCP: False,
        }
    }
    with bond_interface(
        name=BOND99, port=["eth1"], extra_iface_state=extra_iface_state
    ) as bond_state:
        assertlib.assert_state_match(bond_state)

    assertlib.assert_absent(BOND99)


@pytest.mark.tier1
def test_create_vlan_over_a_bond_port(bond99_with_eth2):
    bond_ifstate = bond99_with_eth2[Interface.KEY][0]
    bond_port_ifname = bond_ifstate[Bond.CONFIG_SUBTREE][Bond.PORT][0]
    vlan_id = 102
    vlan_iface_name = "{}.{}".format(bond_port_ifname, vlan_id)
    with vlan_interface(
        vlan_iface_name, vlan_id, bond_port_ifname
    ) as desired_state:
        assertlib.assert_state_match(desired_state)
    assertlib.assert_state_match(bond99_with_eth2)


@pytest.mark.tier1
def test_create_linux_bridge_over_bond(bond99_with_eth2):
    port_state = {
        "stp-hairpin-mode": False,
        "stp-path-cost": 100,
        "stp-priority": 32,
    }
    bridge_name = "linux-br0"
    bridge_state = add_port_to_bridge(
        create_bridge_subtree_state(), BOND99, port_state
    )
    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
def test_preserve_bond_after_bridge_removal(bond99_with_eth2):
    bridge_name = "linux-br0"
    bridge_state = add_port_to_bridge(create_bridge_subtree_state(), BOND99)
    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state_match(desired_state)
    assertlib.assert_state_match(bond99_with_eth2)


@pytest.mark.tier1
def test_create_vlan_over_a_bond(bond99_with_eth2):
    vlan_base_iface = bond99_with_eth2[Interface.KEY][0][Interface.NAME]
    vlan_id = 102
    vlan_iface_name = "{}.{}".format(vlan_base_iface, vlan_id)
    with vlan_interface(
        vlan_iface_name, vlan_id, vlan_base_iface
    ) as desired_state:
        assertlib.assert_state_match(desired_state)
    assertlib.assert_state_match(bond99_with_eth2)


@pytest.mark.tier1
def test_change_bond_option_miimon(bond99_with_2_port):
    desired_state = statelib.show_only((BOND99,))
    iface_state = desired_state[Interface.KEY][0]
    bond_options = iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
    bond_options["miimon"] = 200
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
def test_change_bond_option_with_an_id_value(bond99_with_eth2):
    option_name = "xmit_hash_policy"
    desired_state = statelib.show_only((BOND99,))
    iface_state = desired_state[Interface.KEY][0]
    iface_state[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.XOR
    iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {option_name: "2"}
    libnmstate.apply(desired_state)
    new_iface_state = statelib.show_only((BOND99,))[Interface.KEY][0]
    new_options = new_iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
    assert new_options.get(option_name) == "layer2+3"


def test_create_bond_without_mode():
    with bond_interface(name=BOND99, port=[], create=False) as state:
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE].pop(Bond.MODE)
        with pytest.raises(NmstateValueError):
            libnmstate.apply(state)


@pytest.mark.tier1
def test_bond_mac_restriction_without_mac_in_desire(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"fail_over_mac": "active"},
            },
        },
    ) as state:
        assertlib.assert_state_match(state)


def test_bond_mac_restriction_with_mac_in_desire(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Interface.MAC: MAC0,
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"fail_over_mac": "active"},
            },
        },
        create=False,
    ) as state:
        with pytest.raises(NmstateValueError):
            libnmstate.apply(state)


@pytest.mark.tier1
def test_bond_mac_restriction_in_desire_mac_in_current(bond99_with_2_port):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"fail_over_mac": "active"},
            },
        },
    ) as state:
        assertlib.assert_state_match(state)


def test_bond_mac_restriction_in_current_mac_in_desire(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"fail_over_mac": "active"},
            },
        },
    ) as state:
        assertlib.assert_state_match(state)
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {Interface.NAME: BOND99, Interface.MAC: MAC0}
                    ]
                }
            )


@pytest.mark.tier1
def test_bond_fail_over_mac_follow(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"fail_over_mac": "follow"},
            },
        },
    ) as state:
        assertlib.assert_state_match(state)


@pytest.mark.tier1
def test_create_bond_with_mac(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={Interface.MAC: MAC0},
    ) as state:
        assertlib.assert_state_match(state)


@pytest.mark.tier1
@pytest.mark.parametrize("ips", ("192.0.2.1,192.0.2.2", "192.0.2.2,192.0.1.1"))
def test_bond_with_arp_ip_target(eth1_up, eth2_up, ips):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {
                    "arp_interval": 1000,
                    "arp_ip_target": ips,
                },
            },
        },
    ) as desired_state:
        assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
def test_create_bond_with_default_miimon_explicitly():
    with bond_interface(
        name=BOND99,
        port=[],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"miimon": 100},
            },
        },
    ) as state:
        assertlib.assert_state_match(state)


@pytest.fixture
def bond99_with_miimon():
    with bond_interface(
        name=BOND99,
        port=[],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"miimon": 101},
            },
        },
    ) as state:
        yield state


def test_change_bond_from_miimon_to_arp_internal(bond99_with_miimon):
    state = bond99_with_miimon
    bond_config = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bond_config[Bond.OPTIONS_SUBTREE] = {
        "miimon": 0,
        "arp_interval": 10,
        "arp_ip_target": IPV4_ADDRESS1,
    }


@pytest.fixture
def bond99_with_arp_internal():
    with bond_interface(
        name=BOND99,
        port=[],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {
                    "arp_interval": 10,
                    "arp_ip_target": IPV4_ADDRESS1,
                },
            },
        },
    ) as state:
        yield state


def test_change_bond_from_arp_internal_to_miimon(bond99_with_miimon):
    state = bond99_with_miimon
    bond_config = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bond_config[Bond.OPTIONS_SUBTREE] = {
        "miimon": 100,
        "arp_interval": 0,
    }


def test_create_bond_with_both_miimon_and_arp_internal():
    with pytest.raises(NmstateValueError):
        with bond_interface(
            name=BOND99,
            port=[],
            extra_iface_state={
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ACTIVE_BACKUP,
                    Bond.OPTIONS_SUBTREE: {
                        "miimon": 100,
                        "arp_interval": 10,
                        "arp_ip_target": IPV4_ADDRESS1,
                    },
                },
            },
        ) as state:
            assertlib.assert_state_match(state)


@pytest.mark.tier1
def test_change_2_port_bond_mode_from_1_to_5():
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ACTIVE_BACKUP},
        },
    ) as state:
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.TLB
        libnmstate.apply(state)


@pytest.mark.tier1
def test_set_miimon_100_on_existing_bond(bond99_with_2_port):
    state = bond99_with_2_port
    bond_config = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bond_config[Bond.OPTIONS_SUBTREE] = {"miimon": 100}
    libnmstate.apply(state)
    assertlib.assert_state_match(state)


@pytest.fixture
def eth1_eth2_with_no_profile():
    yield
    ifaces_init(ETH1, ETH2)


def _nmcli_simulate_boot(ifname):
    """
    Use nmcli to reactivate the profile to simulate the server reboot.
    """
    cmdlib.exec_cmd(["nmcli", "connection", "down", ifname], check=True)
    # Wait port been deactivated
    time.sleep(1)
    cmdlib.exec_cmd(["nmcli", "connection", "up", ifname], check=True)
    # Wait port been activated
    time.sleep(1)


# TODO: This test case has random failure in Github CI and NMCI environment,
#       considering this is a ovirt use case which holds low priority,
#       we remove it from tier1 temporary till issue been resolved.
# @pytest.mark.tier1
def test_new_bond_uses_mac_of_first_port_by_name(eth1_eth2_with_no_profile):
    """
    On system boot, NetworkManager will by default activate port in the
    order of their name. Nmstate should provide the consistent MAC address for
    bond regardless the order of port.
    """
    eth1_mac = get_mac_address(ETH1)
    with bond_interface(
        name=BOND99,
        port=[ETH2, ETH1],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN}
        },
    ):
        assert retry_till_true_or_timeout(
            RETRY_TIMEOUT, iface_is_holding_expected_mac, BOND99, eth1_mac
        )
        _nmcli_simulate_boot(BOND99)
        assert retry_till_true_or_timeout(
            RETRY_TIMEOUT, iface_is_holding_expected_mac, BOND99, eth1_mac
        )

    ifaces_init(ETH1, ETH2)

    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN}
        },
    ):
        assert retry_till_true_or_timeout(
            RETRY_TIMEOUT, iface_is_holding_expected_mac, BOND99, eth1_mac
        )
        _nmcli_simulate_boot(BOND99)
        assert retry_till_true_or_timeout(
            RETRY_TIMEOUT, iface_is_holding_expected_mac, BOND99, eth1_mac
        )


@pytest.fixture
def bond99_with_2_port_and_arp_monitor(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {
                    "arp_interval": 60,
                    "arp_ip_target": IPV4_ADDRESS1,
                },
            },
        },
    ) as state:
        yield state


def test_bond_disable_arp_interval(bond99_with_2_port_and_arp_monitor):
    state = bond99_with_2_port_and_arp_monitor
    bond_config = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bond_config[Bond.OPTIONS_SUBTREE]["arp_interval"] = 0
    bond_config[Bond.OPTIONS_SUBTREE]["arp_ip_target"] = ""

    libnmstate.apply(state)

    assertlib.assert_state_match(state)


@pytest.fixture
def bond99_with_2_port_and_lacp_rate(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.LACP,
                Bond.OPTIONS_SUBTREE: {"lacp_rate": "fast"},
            },
        },
    ) as state:
        yield state


@pytest.mark.tier1
def test_bond_switch_mode_with_conflict_option(
    bond99_with_2_port_and_lacp_rate,
):
    state = bond99_with_2_port_and_lacp_rate
    bond_config = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bond_config[Bond.MODE] = BondMode.ROUND_ROBIN
    bond_config[Bond.OPTIONS_SUBTREE] = {"miimon": "140"}

    libnmstate.apply(state)

    assertlib.assert_state_match(state)
    current_state = statelib.show_only((BOND99,))
    current_bond_config = current_state[Interface.KEY][0][Bond.CONFIG_SUBTREE]

    assert "lacp_rate" not in current_bond_config[Bond.OPTIONS_SUBTREE]


def test_add_invalid_port_ip_config(eth1_up):
    d_state = eth1_up
    d_state[Interface.KEY][0][Interface.IPV4][InterfaceIPv4.ENABLED] = True
    d_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.DHCP] = True
    with pytest.raises(NmstateValueError):
        with bond_interface(
            name=BOND99, port=[ETH1], create=False
        ) as bond_state:
            d_state[Interface.KEY].append(bond_state[Interface.KEY][0])
            libnmstate.apply(d_state)


@pytest.fixture
def bond99_mode4_with_2_port(eth1_up, eth2_up):
    port = [
        eth1_up[Interface.KEY][0][Interface.NAME],
        eth2_up[Interface.KEY][0][Interface.NAME],
    ]
    extra_iface_state = {Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP}}
    with bond_interface(
        BOND99, port, extra_iface_state=extra_iface_state
    ) as state:
        yield state


@pytest.mark.tier1
def test_remove_mode4_bond_and_create_mode5_with_the_same_port(
    bond99_mode4_with_2_port,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND99,
                    Interface.TYPE: InterfaceType.BOND,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    extra_iface_state = {Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.TLB}}
    port = bond99_mode4_with_2_port[Interface.KEY][0][Bond.CONFIG_SUBTREE][
        Bond.PORT
    ]
    with bond_interface(
        BOND99, port, extra_iface_state=extra_iface_state
    ) as state:
        assertlib.assert_state_match(state)


@pytest.fixture
def bond99_with_ports_and_vlans(bond99_with_2_port):
    desired_state = bond99_with_2_port
    vlan_iface_info = {
        Interface.NAME: TEST_VLAN,
        Interface.TYPE: InterfaceType.VLAN,
        VLAN.CONFIG_SUBTREE: {VLAN.ID: TEST_VLAN_ID, VLAN.BASE_IFACE: BOND99},
    }
    libnmstate.apply({Interface.KEY: [vlan_iface_info]})
    desired_state[Interface.KEY].append(vlan_iface_info)
    yield desired_state
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VLAN,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


@pytest.mark.tier1
def test_change_bond_mode_does_not_remove_child(bond99_with_ports_and_vlans):
    # Due to bug https://bugzilla.redhat.com/show_bug.cgi?id=1881318
    # Applying twice the desire state is the key to reproduce the problem
    desired_state = bond99_with_ports_and_vlans
    libnmstate.apply(desired_state)

    bond_iface_info = desired_state[Interface.KEY][0]
    bond_iface_info[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.ACTIVE_BACKUP
    libnmstate.apply({Interface.KEY: [bond_iface_info]})
    assertlib.assert_state_match(desired_state)


def test_reset_bond_options_back_to_default(bond99_with_2_port):
    state = statelib.show_only((BOND99,))
    default_miimon = state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
        Bond.OPTIONS_SUBTREE
    ]["miimon"]

    state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE][
        "miimon"
    ] = (default_miimon * 2)

    # Change to non-default miimon value
    libnmstate.apply(state)
    state = statelib.show_only((BOND99,))
    assert (
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE][
            "miimon"
        ]
        == default_miimon * 2
    )

    # Revert to default
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND99,
                    Bond.CONFIG_SUBTREE: {
                        Bond.MODE: BondMode.ROUND_ROBIN,
                        Bond.OPTIONS_SUBTREE: {},
                    },
                }
            ]
        }
    )

    state = statelib.show_only((BOND99,))
    assert (
        default_miimon
        == state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE][
            "miimon"
        ]
    )


@pytest.mark.tier1
def test_ignore_verification_error_on_invalid_bond_option(eth1_up, eth2_up):
    port = [
        eth1_up[Interface.KEY][0][Interface.NAME],
        eth2_up[Interface.KEY][0][Interface.NAME],
    ]
    extra_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ACTIVE_BACKUP,
            Bond.OPTIONS_SUBTREE: {
                # xmit_hash_policy is only valid in
                # balance-xor, 802.3ad, and tlb modes.
                "xmit_hash_policy": "layer2+3",
            },
        }
    }
    with bond_interface(BOND99, port, extra_iface_state=extra_iface_state):
        state = statelib.show_only((BOND99,))
        assert (
            "xmit_hash_policy"
            not in state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.OPTIONS_SUBTREE
            ]
        )


def _nmcli_get_bond_options(ifname):
    rc, output, _ = cmdlib.exec_cmd(
        f"nmcli -g bond.options c show {ifname}".split(), check=True
    )
    return output


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="xmit hash policy vlan+srcmac is only supported in upstream kernel",
)
def test_set_xmit_hash_policy_to_vlan_srcmac(eth1_up, eth2_up):
    port = [
        eth1_up[Interface.KEY][0][Interface.NAME],
        eth2_up[Interface.KEY][0][Interface.NAME],
    ]
    extra_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.XOR,
            Bond.OPTIONS_SUBTREE: {
                "xmit_hash_policy": "vlan+srcmac",
            },
        }
    }
    with bond_interface(BOND99, port, extra_iface_state=extra_iface_state):
        options = _nmcli_get_bond_options(BOND99)
        assert "vlan+srcmac" in options


@pytest.mark.tier1
def test_create_bond_with_copy_mac_from(eth1_up, eth2_up):
    eth2_mac = eth2_up[Interface.KEY][0][Interface.MAC]

    with bond_interface(
        BOND99,
        ["eth1", "eth2"],
        extra_iface_state={Interface.COPY_MAC_FROM: "eth2"},
    ):
        current_state = statelib.show_only((BOND99,))
        assert_mac_address(current_state, eth2_mac)


def _check_mac(iface_name, expected_mac):
    current_state = statelib.show_only((iface_name,))
    return current_state[Interface.KEY][0][Interface.MAC] == expected_mac


def test_replacing_port_set_mac_of_new_port_on_bond(bond99_with_eth2, eth1_up):
    desired_state = bond99_with_eth2
    bond_state = desired_state[Interface.KEY][0]
    eth1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    bond_state[Bond.CONFIG_SUBTREE][Bond.PORT] = [eth1_name]

    libnmstate.apply(desired_state)
    # It takes some time for NM to changing bond MAC after port attached.
    assert retry_till_true_or_timeout(
        10,  # timeout
        _check_mac,
        bond_state[Interface.NAME],
        eth1_up[Interface.KEY][0][Interface.MAC],
    )


@pytest.mark.tier1
def test_bond_enable_and_disable_accept_all_mac_addresses(bond88_with_port):
    desired_state = bond88_with_port
    desired_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = True
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    desired_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = False
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
def test_bond_flip_tlb_dynamic_lbs(bond99_with_2_port):
    desired_state = bond99_with_2_port
    bond_state = desired_state[Interface.KEY][0]
    bond_state[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.TLB
    bond_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
        "tlb_dynamic_lb": True
    }

    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    bond_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
        "tlb_dynamic_lb": False
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_bond_preserve_existing_all_slaves_active_setting(bond99_with_2_port):
    desired_state = bond99_with_2_port
    bond_state = desired_state[Interface.KEY][0]
    bond_state[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.TLB
    bond_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
        "all_slaves_active": "dropped",
    }

    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    bond_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
        "tlb_dynamic_lb": False
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)
    current_state = statelib.show_only((BOND99,))
    assert (
        current_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
            Bond.OPTIONS_SUBTREE
        ]["all_slaves_active"]
        == "dropped"
    )


@pytest.mark.tier1
def test_bond_mac_restriction_check_only_impact_desired(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        port=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"fail_over_mac": "active"},
            },
        },
    ):
        dummy_iface_state = {
            Interface.NAME: "dummy0",
            Interface.TYPE: InterfaceType.DUMMY,
            Interface.STATE: InterfaceState.UP,
        }
        try:
            libnmstate.apply({Interface.KEY: [dummy_iface_state]})
        finally:
            dummy_iface_state[Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply({Interface.KEY: [dummy_iface_state]})


def test_bond_ad_actor_system_with_multicast_mac_address(bond99_with_2_port):
    desired_state = bond99_with_2_port
    bond_state = desired_state[Interface.KEY][0]
    bond_state[Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.LACP
    bond_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE] = {
        "ad_actor_system": "01:00:5E:00:0f:01"
    }

    with pytest.raises(NmstateValueError):
        libnmstate.apply(desired_state)


@pytest.mark.tier1
def test_create_bond_with_copy_mac_from_bond_port_perm_hwaddr(
    eth1_up, eth2_up
):
    eth1_mac = eth1_up[Interface.KEY][0][Interface.MAC]
    eth2_mac = eth2_up[Interface.KEY][0][Interface.MAC]

    with bond_interface(
        BOND99,
        ["eth1", "eth2"],
        extra_iface_state={Interface.COPY_MAC_FROM: "eth2"},
    ):
        current_state = statelib.show_only((BOND99,))
        assert_mac_address(current_state, eth2_mac)
        with bond_interface(
            BOND99,
            ["eth1", "eth2"],
            extra_iface_state={Interface.COPY_MAC_FROM: "eth1"},
        ):
            current_state = statelib.show_only((BOND99,))
            assert_mac_address(current_state, eth1_mac)


def test_down_dettached_bond_port_preserve_config(bond99_with_2_port):
    absent_bond_down_port_state = yaml.load(
        """
---
interfaces:
- name: bond99
  type: bond
  state: absent
- name: eth1
  state: down
  ipv4:
    enabled: true
    dhcp: true
- name: eth2
  state: down""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(absent_bond_down_port_state)

    up_eth1_state = yaml.load(
        """
---
interfaces:
- name: eth1
  state: up""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(up_eth1_state)

    expected_state = yaml.load(
        """
---
interfaces:
- name: eth1
  state: up
  ipv4:
    enabled: true
    dhcp: true""",
        Loader=yaml.SafeLoader,
    )
    assertlib.assert_state_match(expected_state)


@pytest.mark.tier1
def test_remove_bond_and_assign_ip_to_bond_port(bond99_with_2_port):
    desired_state = yaml.load(
        """---
        interfaces:
          - name: bond99
            state: absent
          - name: eth1
            type: ethernet
            state: up
            mtu: 1500
            ipv4:
              enabled: true
              dhcp: false
              address:
              - ip: 192.168.1.1
                prefix-length: 24
            ipv6:
              enabled: true
              dhcp: false
              autoconf: false
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or nm_minor_version() < 43,
    reason="bond arp_missed_max is not supported by "
    "Github CI Ubuntu 5.15 kernel",
)
def test_change_bond_option_arp_missed_max(bond99_with_2_port):
    desired_state = statelib.show_only((BOND99,))
    iface_state = desired_state[Interface.KEY][0]
    bond_options = iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
    bond_options["arp_missed_max"] = 200
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_change_mtu_of_bond_port(bond99_with_2_port):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.STATE: InterfaceState.UP,
                    Interface.MTU: 1280,
                }
            ]
        }
    )


@pytest.fixture
def cleanup_bond99():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND99,
                    Interface.TYPE: InterfaceType.BOND,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


def test_create_bond_with_port_refered_by_mac(
    eth1_up, eth2_up, cleanup_bond99
):
    eth1_mac = get_mac_address("eth1")
    eth2_mac = get_mac_address("eth2")
    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: bond99-port1
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: {eth1_mac}
        - name: bond99-port2
          type: ethernet
          state: up
          identifier: mac-address
          mac-address: {eth2_mac}
        - name: bond99
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            ports-config:
              - profile-name: bond99-port1
              - profile-name: bond99-port2
        """
    )
    libnmstate.apply(desired_state)
    cur_iface = statelib.show_only((BOND99,))[Interface.KEY][0]

    assert cur_iface[Bond.CONFIG_SUBTREE][Bond.PORT] == ["eth1", "eth2"]
