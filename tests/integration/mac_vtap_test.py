# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2020 Red Hat, Inc.
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
