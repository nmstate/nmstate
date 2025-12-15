# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import MacVlan

from .testlib import assertlib


ETH1 = "eth1"
MACVLAN0 = "macvlan0"


@pytest.mark.parametrize(
    "mode",
    [
        MacVlan.Mode.VEPA,
        MacVlan.Mode.BRIDGE,
        MacVlan.Mode.PRIVATE,
        MacVlan.Mode.PASSTHRU,
    ],
)
def test_add_mac_vlan_multiple_modes(eth1_up, mode):
    with macvlan_interface(MACVLAN0, mode, True) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_absent(MACVLAN0)


def test_add_mac_vlan_promiscuous_off(eth1_up):
    with macvlan_interface(
        MACVLAN0, MacVlan.Mode.PASSTHRU, False
    ) as desired_state:
        libnmstate.apply(desired_state)
    assertlib.assert_absent(MACVLAN0)


def test_edit_mac_vlan_(eth1_up):
    with macvlan_interface(
        MACVLAN0, MacVlan.Mode.PASSTHRU, True
    ) as desired_state:
        assertlib.assert_state(desired_state)
        desired_state[Interface.KEY][0][Interface.MTU] = 1400
        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(MACVLAN0)


@contextmanager
def macvlan_interface(ifname, mode, promiscuous):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: MacVlan.TYPE,
                Interface.STATE: InterfaceState.UP,
                MacVlan.CONFIG_SUBTREE: {
                    MacVlan.BASE_IFACE: ETH1,
                    MacVlan.MODE: mode,
                    MacVlan.PROMISCUOUS: promiscuous,
                },
            }
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)
