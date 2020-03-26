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
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import statelib
from .testlib.assertlib import assert_mac_address
from .testlib.bondlib import bond_interface
from .testlib.ifacelib import get_mac_address
from .testlib.ifacelib import ifaces_init
from .testlib.vlan import vlan_interface

from .testlib.bridgelib import linux_bridge
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import create_bridge_subtree_state

BOND99 = "bond99"
ETH1 = "eth1"
ETH2 = "eth2"

MAC0 = "02:FF:FF:FF:FF:00"
MAC1 = "02:FF:FF:FF:FF:01"

IPV4_ADDRESS1 = "192.0.2.251"

BOND99_YAML_BASE = """
interfaces:
- name: bond99
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    slaves:
    - eth1
    - eth2
"""


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
def bond99_with_2_slaves(eth1_up, eth2_up):
    slaves = [
        eth1_up[Interface.KEY][0][Interface.NAME],
        eth2_up[Interface.KEY][0][Interface.NAME],
    ]
    with bond_interface(BOND99, slaves) as state:
        yield state


@pytest.fixture
def bond88_with_slave(eth1_up):
    slaves = [eth1_up[Interface.KEY][0][Interface.NAME]]
    with bond_interface(BOND99, slaves) as state:
        yield state


@pytest.fixture
def bond99_with_eth2(eth2_up):
    slaves = [eth2_up[Interface.KEY][0][Interface.NAME]]
    with bond_interface(BOND99, slaves) as state:
        yield state


def test_add_and_remove_bond_with_two_slaves(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE, Loader=yaml.SafeLoader)
    libnmstate.apply(state)

    assertlib.assert_state(state)

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


def test_add_bond_without_slaves():
    with bond_interface(name=BOND99, slaves=[]) as state:

        assert state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.SLAVES] == []


def test_add_bond_with_slaves_and_ipv4(eth1_up, eth2_up, setup_remove_bond99):
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
                    Bond.SLAVES: [
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
                    Bond.SLAVES: [
                        eth1_up[Interface.KEY][0][Interface.NAME],
                        eth2_up[Interface.KEY][0][Interface.NAME],
                    ],
                    Bond.OPTIONS_SUBTREE: {"miimon": "140"},
                },
            }
        ]
    }

    desired_state[Interface.KEY][0]["invalid_key"] = "foo"

    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(desired_state)

    time.sleep(5)

    current_state_after_apply = libnmstate.show()
    assert (
        current_state[Interface.KEY]
        == current_state_after_apply[Interface.KEY]
    )


def test_add_slave_to_bond_without_slaves(eth1_up):
    slave_name = eth1_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, slaves=[]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [slave_name]
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == [slave_name]


@pytest.mark.xfail(strict=True, reason="Jira issue # NMSTATE-143")
def test_remove_all_slaves_from_bond(eth1_up):
    slave_name = (eth1_up[Interface.KEY][0][Interface.NAME],)
    with bond_interface(name=BOND99, slaves=[slave_name]) as state:
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.SLAVES] = []

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == []


def test_replace_bond_slave(eth1_up, eth2_up):
    slave1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    slave2_name = eth2_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, slaves=[slave1_name]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [slave2_name]

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == [
            slave2_name
        ]


def test_remove_one_of_the_bond_slaves(eth1_up, eth2_up):
    slave1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    slave2_name = eth2_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(
        name=BOND99, slaves=[slave1_name, slave2_name]
    ) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [slave2_name]

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

    assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == [slave2_name]


def test_swap_slaves_between_bonds(bond88_with_slave, bond99_with_eth2):
    bonding88 = bond88_with_slave[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bonding99 = bond99_with_eth2[Interface.KEY][0][Bond.CONFIG_SUBTREE]

    bonding88[Bond.SLAVES], bonding99[Bond.SLAVES] = (
        bonding99[Bond.SLAVES],
        bonding88[Bond.SLAVES],
    )

    state = bond88_with_slave
    state.update(bond99_with_eth2)
    libnmstate.apply(state)

    assertlib.assert_state_match(state)


def test_set_bond_mac_address(eth1_up):
    slave_name = eth1_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, slaves=[slave_name]) as state:
        state[Interface.KEY][0][Interface.MAC] = MAC0
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99, slave_name))
        assert_mac_address(current_state, MAC0)

        state[Interface.KEY][0][Interface.MAC] = MAC1
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99, slave_name))
        assert_mac_address(current_state, MAC1)


def test_changing_slave_order_keeps_mac_of_existing_bond(bond99_with_2_slaves):
    bond_state = bond99_with_2_slaves[Interface.KEY][0]
    bond_slaves = bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES]
    ifaces_names = [bond_state[Interface.NAME]] + bond_slaves

    current_state = statelib.show_only(ifaces_names)
    assert_mac_address(current_state)

    bond_slaves.reverse()
    libnmstate.apply(bond99_with_2_slaves)

    modified_state = statelib.show_only(ifaces_names)
    assert_mac_address(
        modified_state, current_state[Interface.KEY][0][Interface.MAC]
    )


@pytest.mark.tier1
def test_adding_a_slave_keeps_mac_of_existing_bond(bond99_with_eth2, eth1_up):
    desired_state = bond99_with_eth2
    bond_state = desired_state[Interface.KEY][0]
    bond_slaves = bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES]
    bond_slaves.insert(0, eth1_up[Interface.KEY][0][Interface.NAME])

    current_state = statelib.show_only((bond_state[Interface.NAME],))

    libnmstate.apply(desired_state)
    modified_state = statelib.show_only((bond_state[Interface.NAME],))
    assert (
        modified_state[Interface.KEY][0][Interface.MAC]
        == current_state[Interface.KEY][0][Interface.MAC]
    )


@pytest.mark.tier1
def test_adding_slaves_to_empty_bond_doesnt_keep_mac(eth1_up):
    with bond_interface(BOND99, []) as state:
        bond_state = state[Interface.KEY][0]
        eth1_name = eth1_up[Interface.KEY][0][Interface.NAME]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [eth1_name]

        current_state = statelib.show_only((bond_state[Interface.NAME],))

        libnmstate.apply(state)
        modified_state = statelib.show_only((bond_state[Interface.NAME],))
        assert (
            modified_state[Interface.KEY][0][Interface.MAC]
            != current_state[Interface.KEY][0][Interface.MAC]
        )


@pytest.mark.tier1
def test_replacing_slaves_keeps_mac_of_existing_bond(
    bond99_with_eth2, eth1_up
):
    desired_state = bond99_with_eth2
    bond_state = desired_state[Interface.KEY][0]
    eth1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [eth1_name]

    current_state = statelib.show_only((bond_state[Interface.NAME],))

    libnmstate.apply(desired_state)
    modified_state = statelib.show_only((bond_state[Interface.NAME],))
    assert (
        modified_state[Interface.KEY][0][Interface.MAC]
        == current_state[Interface.KEY][0][Interface.MAC]
    )


def test_removing_slaves_keeps_mac_of_existing_bond(
    bond99_with_2_slaves, eth1_up
):
    desired_state = bond99_with_2_slaves
    bond_state = desired_state[Interface.KEY][0]
    eth1_name = eth1_up[Interface.KEY][0][Interface.NAME]
    bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [eth1_name]

    current_state = statelib.show_only((bond_state[Interface.NAME],))

    libnmstate.apply(desired_state)
    modified_state = statelib.show_only((bond_state[Interface.NAME],))
    assert (
        modified_state[Interface.KEY][0][Interface.MAC]
        == current_state[Interface.KEY][0][Interface.MAC]
    )


def test_bond_with_empty_ipv6_static_address(eth1_up):
    extra_iface_state = {
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.AUTOCONF: False,
            InterfaceIPv6.DHCP: False,
        }
    }
    with bond_interface(
        name=BOND99, slaves=["eth1"], extra_iface_state=extra_iface_state
    ) as bond_state:
        assertlib.assert_state(bond_state)

    assertlib.assert_absent(BOND99)


def test_create_vlan_over_a_bond_slave(bond99_with_eth2):
    bond_ifstate = bond99_with_eth2[Interface.KEY][0]
    bond_slave_ifname = bond_ifstate[Bond.CONFIG_SUBTREE][Bond.SLAVES][0]
    vlan_id = 102
    vlan_iface_name = "{}.{}".format(bond_slave_ifname, vlan_id)
    with vlan_interface(
        vlan_iface_name, vlan_id, bond_slave_ifname
    ) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_state(bond99_with_eth2)


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
        assertlib.assert_state(desired_state)


def test_preserve_bond_after_bridge_removal(bond99_with_eth2):
    bridge_name = "linux-br0"
    bridge_state = add_port_to_bridge(create_bridge_subtree_state(), BOND99)
    with linux_bridge(bridge_name, bridge_state) as desired_state:
        assertlib.assert_state_match(desired_state)
    assertlib.assert_state_match(bond99_with_eth2)


def test_create_vlan_over_a_bond(bond99_with_eth2):
    vlan_base_iface = bond99_with_eth2[Interface.KEY][0][Interface.NAME]
    vlan_id = 102
    vlan_iface_name = "{}.{}".format(vlan_base_iface, vlan_id)
    with vlan_interface(
        vlan_iface_name, vlan_id, vlan_base_iface
    ) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_state(bond99_with_eth2)


def test_change_bond_option_miimon(bond99_with_2_slaves):
    desired_state = statelib.show_only((BOND99,))
    iface_state = desired_state[Interface.KEY][0]
    bond_options = iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
    bond_options["miimon"] = 200
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_change_bond_option_with_an_id_value(bond99_with_eth2):
    option_name = "xmit_hash_policy"
    desired_state = statelib.show_only((BOND99,))
    iface_state = desired_state[Interface.KEY][0]
    bond_options = iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
    bond_options[option_name] = "2"
    libnmstate.apply(desired_state)
    new_iface_state = statelib.show_only((BOND99,))[Interface.KEY][0]
    new_options = new_iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
    assert new_options.get(option_name) == "layer2+3"


def test_create_bond_without_mode():
    with bond_interface(name=BOND99, slaves=[], create=False) as state:
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE].pop(Bond.MODE)
        with pytest.raises(NmstateValueError):
            libnmstate.apply(state)


def test_bond_mac_restriction_without_mac_in_desire(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
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
        slaves=[ETH1, ETH2],
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


def test_bond_mac_restriction_in_desire_mac_in_current(bond99_with_2_slaves):
    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
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
        slaves=[ETH1, ETH2],
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


def test_create_bond_with_mac(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
        extra_iface_state={Interface.MAC: MAC0},
    ) as state:
        assertlib.assert_state_match(state)


@pytest.mark.parametrize("ips", ("192.0.2.1,192.0.2.2", "192.0.2.2,192.0.1.1"))
def test_bond_with_arp_ip_target(eth1_up, eth2_up, ips):
    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
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


def test_create_bond_with_default_miimon_explicitly():
    with bond_interface(
        name=BOND99,
        slaves=[],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: BondMode.ACTIVE_BACKUP,
                Bond.OPTIONS_SUBTREE: {"miimon": 100},
            },
        },
    ) as state:
        assertlib.assert_state_match(state)


def test_change_2_slaves_bond_mode_from_1_to_5():
    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ACTIVE_BACKUP}
        },
    ) as state:
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.MODE] = BondMode.TLB
        libnmstate.apply(state)


def test_set_miimon_100_on_existing_bond(bond99_with_2_slaves):
    state = bond99_with_2_slaves
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
    # Wait slave been deactivated
    time.sleep(1)
    cmdlib.exec_cmd(["nmcli", "connection", "up", ifname], check=True)
    # Wait slave been activated
    time.sleep(1)


def test_new_bond_uses_mac_of_first_slave_by_name(eth1_eth2_with_no_profile):
    """
    On system boot, NetworkManager will by default activate slaves in the
    order of their name. Nmstate should provide the consistent MAC address for
    bond regardless the order of slaves.
    """
    eth1_mac = get_mac_address(ETH1)
    with bond_interface(
        name=BOND99,
        slaves=[ETH2, ETH1],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN}
        },
    ):
        assert get_mac_address(BOND99) == eth1_mac
        _nmcli_simulate_boot(BOND99)
        assert get_mac_address(BOND99) == eth1_mac

    ifaces_init(ETH1, ETH2)

    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
        extra_iface_state={
            Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN}
        },
    ):
        assert get_mac_address(BOND99) == eth1_mac
        _nmcli_simulate_boot(BOND99)
        assert get_mac_address(BOND99) == eth1_mac


@pytest.fixture
def bond99_with_2_slaves_and_arp_monitor(eth1_up, eth2_up):
    with bond_interface(
        name=BOND99,
        slaves=[ETH1, ETH2],
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


def test_bond_disable_arp_interval(bond99_with_2_slaves_and_arp_monitor):
    state = bond99_with_2_slaves_and_arp_monitor
    bond_config = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bond_config[Bond.OPTIONS_SUBTREE]["arp_interval"] = 0
    bond_config[Bond.OPTIONS_SUBTREE]["arp_ip_target"] = ""

    libnmstate.apply(state)

    assertlib.assert_state_match(state)
