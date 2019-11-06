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
import time

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import VLAN
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from .testlib import assertlib
from .testlib import statelib
from .testlib.assertlib import assert_mac_address
from .testlib.vlan import vlan_interface

VLAN_IFNAME = 'eth1.101'
VLAN2_IFNAME = 'eth1.102'


def test_add_and_remove_vlan(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ) as desired_state:
        assertlib.assert_state(desired_state)

    current_state = statelib.show_only((VLAN_IFNAME,))
    assert not current_state[Interface.KEY]


@pytest.fixture
def vlan_on_eth1(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ) as desired_state:
        base_iface_name = desired_state[Interface.KEY][0][VLAN.CONFIG_SUBTREE][
            VLAN.BASE_IFACE
        ]
        iface_states = statelib.show_only((base_iface_name, VLAN_IFNAME))
        yield iface_states


def test_vlan_iface_uses_the_mac_of_base_iface(vlan_on_eth1):
    assert_mac_address(vlan_on_eth1)


def test_add_and_remove_two_vlans_on_same_iface(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        assertlib.assert_state(desired_state)

    vlan_interfaces = [i[Interface.NAME] for i in desired_state[Interface.KEY]]
    current_state = statelib.show_only(vlan_interfaces)
    assert not current_state[Interface.KEY]


def test_two_vlans_on_eth1_change_mtu(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_state = desired_state[Interface.KEY][0]
    vlans_state = create_two_vlans_state()
    desired_state[Interface.KEY].extend(vlans_state[Interface.KEY])
    for iface in desired_state[Interface.KEY]:
        iface[Interface.MTU] = 2000
    libnmstate.apply(desired_state)

    eth1_102_state = next(
        ifstate
        for ifstate in desired_state[Interface.KEY]
        if ifstate[Interface.NAME] == VLAN2_IFNAME
    )
    eth1_state[Interface.MTU] = 2200
    eth1_102_state[Interface.MTU] = 2200
    libnmstate.apply(desired_state)

    eth1_vlan_iface_cstate = statelib.show_only((VLAN_IFNAME,))
    assert eth1_vlan_iface_cstate[Interface.KEY][0][Interface.MTU] == 2000


def test_two_vlans_on_eth1_change_base_iface_mtu(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_state = desired_state[Interface.KEY][0]
    vlans_state = create_two_vlans_state()
    desired_state[Interface.KEY].extend(vlans_state[Interface.KEY])
    for iface in desired_state[Interface.KEY]:
        iface[Interface.MTU] = 2000
    libnmstate.apply(desired_state)

    eth1_state[Interface.MTU] = 2200
    libnmstate.apply({Interface.KEY: [eth1_state]})
    eth1_vlan_iface_cstate = statelib.show_only((VLAN_IFNAME,))
    assert eth1_vlan_iface_cstate[Interface.KEY][0][Interface.MTU] == 2000


def test_two_vlans_on_eth1_change_mtu_rollback(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    vlans_state = create_two_vlans_state()
    desired_state[Interface.KEY].extend(vlans_state[Interface.KEY])
    for iface in desired_state[Interface.KEY]:
        iface[Interface.MTU] = 2000
    libnmstate.apply(desired_state)

    for iface in desired_state[Interface.KEY]:
        iface[Interface.MTU] = 2200
    libnmstate.apply(desired_state, commit=False)
    libnmstate.rollback()

    eth1_vlan_iface_cstate = statelib.show_only((VLAN_IFNAME,))
    assert eth1_vlan_iface_cstate[Interface.KEY][0][Interface.MTU] == 2000


def test_rollback_for_vlans(eth1_up):
    current_state = libnmstate.show()
    desired_state = create_two_vlans_state()

    desired_state[Interface.KEY][1]['invalid_key'] = 'foo'
    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(desired_state)

    time.sleep(5)  # Give some time for NetworkManager to rollback
    current_state_after_apply = libnmstate.show()
    assert current_state == current_state_after_apply


def test_set_vlan_iface_down(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: VLAN_IFNAME,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )

        current_state = statelib.show_only((VLAN_IFNAME,))
        assert not current_state[Interface.KEY]


def test_add_new_base_iface_with_vlan():
    iface_base = 'dummy00'
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: 'dummy00.101',
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {
                    VLAN.ID: 101,
                    VLAN.BASE_IFACE: iface_base,
                },
            },
            {
                Interface.NAME: iface_base,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
            },
        ]
    }
    try:
        libnmstate.apply(desired_state)
    finally:
        for ifstate in desired_state[Interface.KEY]:
            ifstate[Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(desired_state, verify_change=False)


@contextmanager
def two_vlans_on_eth1():
    desired_state = create_two_vlans_state()
    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: VLAN_IFNAME,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                    {
                        Interface.NAME: VLAN2_IFNAME,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                ]
            }
        )


def create_two_vlans_state():
    return {
        Interface.KEY: [
            {
                Interface.NAME: VLAN_IFNAME,
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: 'eth1'},
            },
            {
                Interface.NAME: VLAN2_IFNAME,
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 102, VLAN.BASE_IFACE: 'eth1'},
            },
        ]
    }
