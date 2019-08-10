#
# Copyright (c) 2018-2019 Red Hat, Inc.
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
import pytest
import time
import yaml

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from .testlib import assertlib
from .testlib import statelib
from .testlib.assertlib import assert_mac_address
from .testlib.env import TEST_NIC1
from .testlib.env import TEST_NIC2


BOND99 = 'bond99'
BOND88 = 'bond88'

MAC0 = '02:ff:ff:ff:ff:00'
MAC1 = '02:ff:ff:ff:ff:01'

BOND99_YAML_BASE = """
interfaces:
- name: bond99
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    slaves:
    - {}
    - {}
""".format(
    TEST_NIC1, TEST_NIC2
)


@pytest.fixture
def setup_remove_bond99():
    yield
    remove_bond = {
        Interface.KEY: [
            {
                Interface.NAME: 'bond99',
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.ABSENT,
            }
        ]
    }
    libnmstate.apply(remove_bond)


@pytest.fixture
def bond99_with_2_slaves(test_nic1_up, test_nic2_up):
    slaves = [TEST_NIC1, TEST_NIC2]
    with bond_interface('bond99', slaves) as state:
        yield state


@pytest.fixture
def bond88_with_slave(test_nic1_up):
    slaves = [TEST_NIC1]
    with bond_interface(BOND88, slaves) as state:
        yield state


@pytest.fixture
def bond99_with_slave(test_nic2_up):
    slaves = [TEST_NIC2]
    with bond_interface(BOND99, slaves) as state:
        yield state


@contextmanager
def bond_interface(name, slaves, extra_iface_state=None):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.SLAVES: slaves,
                },
            }
        ]
    }
    if extra_iface_state:
        desired_state[Interface.KEY][0].update(extra_iface_state)

    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: name,
                        Interface.TYPE: InterfaceType.BOND,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )


def test_add_and_remove_bond_with_two_slaves(test_nic1_up, test_nic2_up):
    state = yaml.load(BOND99_YAML_BASE, Loader=yaml.SafeLoader)
    libnmstate.apply(state)

    assertlib.assert_state(state)

    state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT

    libnmstate.apply(state)

    state = statelib.show_only((state[Interface.KEY][0][Interface.NAME],))
    assert not state[Interface.KEY]


def test_remove_bond_with_minimum_desired_state(test_nic1_up, test_nic2_up):
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
    with bond_interface(name='bond99', slaves=[]) as state:

        assert state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.SLAVES] == []


def test_add_bond_with_slaves_and_ipv4(
    test_nic1_up, test_nic2_up, setup_remove_bond99
):
    desired_bond_state = {
        Interface.KEY: [
            {
                Interface.NAME: 'bond99',
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: '192.168.122.250',
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.SLAVES: [
                        TEST_NIC1,
                        TEST_NIC2,
                    ],
                    Bond.OPTIONS_SUBTREE: {'miimon': '140'},
                },
            }
        ]
    }

    libnmstate.apply(desired_bond_state)

    assertlib.assert_state(desired_bond_state)


def test_rollback_for_bond(test_nic1_up, test_nic2_up):
    current_state = libnmstate.show()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: 'bond99',
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: '192.168.122.250',
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.SLAVES: [
                        TEST_NIC1,
                        TEST_NIC2,
                    ],
                    Bond.OPTIONS_SUBTREE: {'miimon': '140'},
                },
            }
        ]
    }

    desired_state[Interface.KEY][0]['invalid_key'] = 'foo'

    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(desired_state)

    time.sleep(5)

    current_state_after_apply = libnmstate.show()
    assert (
        current_state[Interface.KEY]
        == current_state_after_apply[Interface.KEY]
    )


def test_add_slave_to_bond_without_slaves(test_nic1_up):
    slave_name = test_nic1_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, slaves=[]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [slave_name]
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == [slave_name]


@pytest.mark.xfail(strict=True, reason="Jira issue # NMSTATE-143")
def test_remove_all_slaves_from_bond(test_nic1_up):
    slave_name = (test_nic1_up[Interface.KEY][0][Interface.NAME],)
    with bond_interface(name=BOND99, slaves=[slave_name]) as state:
        state[Interface.KEY][0][Bond.CONFIG_SUBTREE][Bond.SLAVES] = []

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == []


def test_replace_bond_slave(test_nic1_up, test_nic2_up):
    slave1_name = test_nic1_up[Interface.KEY][0][Interface.NAME]
    slave2_name = test_nic2_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, slaves=[slave1_name]) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [slave2_name]

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

        assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == [
            slave2_name
        ]


def test_remove_one_of_the_bond_slaves(test_nic1_up, test_nic2_up):
    slave1_name = test_nic1_up[Interface.KEY][0][Interface.NAME]
    slave2_name = test_nic2_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(
        name=BOND99, slaves=[slave1_name, slave2_name]
    ) as state:
        bond_state = state[Interface.KEY][0]
        bond_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] = [slave2_name]

        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99,))
        bond_cur_state = current_state[Interface.KEY][0]

    assert bond_cur_state[Bond.CONFIG_SUBTREE][Bond.SLAVES] == [slave2_name]


def test_swap_slaves_between_bonds(bond88_with_slave, bond99_with_slave):
    bonding88 = bond88_with_slave[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    bonding99 = bond99_with_slave[Interface.KEY][0][Bond.CONFIG_SUBTREE]

    bonding88[Bond.SLAVES], bonding99[Bond.SLAVES] = (
        bonding99[Bond.SLAVES],
        bonding88[Bond.SLAVES],
    )

    state = bond88_with_slave
    state.update(bond99_with_slave)
    libnmstate.apply(state)

    assertlib.assert_state(state)


def test_set_bond_mac_address(test_nic1_up):
    slave_name = test_nic1_up[Interface.KEY][0][Interface.NAME]
    with bond_interface(name=BOND99, slaves=[slave_name]) as state:
        state[Interface.KEY][0][Interface.MAC] = MAC0
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99, slave_name))
        assert_mac_address(current_state, MAC0)

        state[Interface.KEY][0][Interface.MAC] = MAC1
        libnmstate.apply(state)

        current_state = statelib.show_only((BOND99, slave_name))
        assert_mac_address(current_state, MAC1)


def test_reordering_the_slaves_does_not_change_the_mac(bond99_with_2_slaves):
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


def test_bond_with_empty_ipv6_static_address(test_nic1_up):
    extra_iface_state = {
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.AUTOCONF: False,
            InterfaceIPv6.DHCP: False,
        }
    }
    with bond_interface(
        name='bond99', slaves=[TEST_NIC1], extra_iface_state=extra_iface_state
    ) as bond_state:
        assertlib.assert_state(bond_state)

    assertlib.assert_absent('bond99')
