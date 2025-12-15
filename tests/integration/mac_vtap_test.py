# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import MacVtap

from .testlib import assertlib


ETH1 = "eth1"
MACVLAN0 = "macvtap0"


@pytest.mark.parametrize(
    "mode",
    [
        MacVtap.Mode.VEPA,
        MacVtap.Mode.BRIDGE,
        MacVtap.Mode.PRIVATE,
        MacVtap.Mode.PASSTHRU,
    ],
)
def test_add_mac_vtap_multiple_modes(eth1_up, mode):
    with macvtap_interface(MACVLAN0, mode, True) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_absent(MACVLAN0)


def test_add_mac_vtap_promiscuous_off(eth1_up):
    with macvtap_interface(
        MACVLAN0, MacVtap.Mode.PASSTHRU, False
    ) as desired_state:
        libnmstate.apply(desired_state)
    assertlib.assert_absent(MACVLAN0)


def test_edit_mac_vtap(eth1_up):
    with macvtap_interface(
        MACVLAN0, MacVtap.Mode.PASSTHRU, True
    ) as desired_state:
        assertlib.assert_state(desired_state)
        desired_state[Interface.KEY][0][Interface.MTU] = 1400
        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(MACVLAN0)


@contextmanager
def macvtap_interface(ifname, mode, promiscuous):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: MacVtap.TYPE,
                Interface.STATE: InterfaceState.UP,
                MacVtap.CONFIG_SUBTREE: {
                    MacVtap.BASE_IFACE: ETH1,
                    MacVtap.MODE: mode,
                    MacVtap.PROMISCUOUS: promiscuous,
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
