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

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES
from .testlib.assertlib import assert_mac_address
from .testlib.vlan import vlan_interface

VLAN_IFNAME = 'eth1.101'
VLAN2_IFNAME = 'eth1.102'

TWO_VLANS_STATE = {
    INTERFACES: [
        {
            'name': VLAN_IFNAME,
            'type': 'vlan',
            'state': 'up',
            VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: 'eth1'},
        },
        {
            'name': VLAN2_IFNAME,
            'type': 'vlan',
            'state': 'up',
            VLAN.CONFIG_SUBTREE: {VLAN.ID: 102, VLAN.BASE_IFACE: 'eth1'},
        },
    ]
}


def test_add_and_remove_vlan(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ) as desired_state:
        assertlib.assert_state(desired_state)

    current_state = statelib.show_only((VLAN_IFNAME,))
    assert not current_state[INTERFACES]


@pytest.fixture
def vlan_on_eth1(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ) as desired_state:
        base_iface_name = desired_state[INTERFACES][0][VLAN.CONFIG_SUBTREE][
            VLAN.BASE_IFACE
        ]
        iface_states = statelib.show_only((base_iface_name, VLAN_IFNAME))
        yield iface_states


def test_vlan_iface_uses_the_mac_of_base_iface(vlan_on_eth1):
    assert_mac_address(vlan_on_eth1)


def test_add_and_remove_two_vlans_on_same_iface(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        assertlib.assert_state(desired_state)

    vlan_interfaces = [i['name'] for i in desired_state[INTERFACES]]
    current_state = statelib.show_only(vlan_interfaces)
    assert not current_state[INTERFACES]


def test_rollback_for_vlans(eth1_up):
    current_state = libnmstate.show()
    desired_state = TWO_VLANS_STATE

    desired_state[INTERFACES][1]['invalid_key'] = 'foo'
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
                INTERFACES: [
                    {'name': VLAN_IFNAME, 'type': 'vlan', 'state': 'down'}
                ]
            }
        )

        current_state = statelib.show_only((VLAN_IFNAME,))
        assert not current_state[INTERFACES]


@contextmanager
def two_vlans_on_eth1():
    desired_state = TWO_VLANS_STATE
    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                INTERFACES: [
                    {'name': VLAN_IFNAME, 'type': 'vlan', 'state': 'absent'},
                    {'name': VLAN2_IFNAME, 'type': 'vlan', 'state': 'absent'},
                ]
            }
        )
