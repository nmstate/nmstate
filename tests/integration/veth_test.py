#
# Copyright (c) 2021 Red Hat, Inc.
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
from libnmstate.error import NmstateLibnmError
from libnmstate.schema import Bridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Veth

from .testlib import assertlib
from .testlib import statelib
from .testlib.env import nm_major_minor_version


VETH1 = "veth1"
VETH1PEER = "veth1peer"
VETH2PEER = "veth2peer"


@pytest.mark.skipif(
    nm_major_minor_version() >= 1.28,
    reason="Modifying veth interfaces is supported on NetworkManager.",
)
@pytest.mark.tier1
def test_add_veth_not_supported():
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: VETH1,
                Interface.TYPE: InterfaceType.VETH,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {Veth.PEER: VETH1PEER},
            }
        ]
    }

    with pytest.raises(NmstateLibnmError):
        libnmstate.apply(desired_state)


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
@pytest.mark.tier1
def test_add_and_remove_veth():
    with veth_interface(VETH1, VETH1PEER) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(VETH1)
    assertlib.assert_absent(VETH1PEER)


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
@pytest.mark.tier1
def test_add_veth_both_up():
    with veth_interface(VETH1, VETH1PEER):
        c_state = statelib.show_only(
            (
                VETH1,
                VETH1PEER,
            )
        )
        assert c_state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
        assert c_state[Interface.KEY][1][Interface.STATE] == InterfaceState.UP

    assertlib.assert_absent(VETH1)
    assertlib.assert_absent(VETH1PEER)


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
@pytest.mark.tier1
def test_add_veth_as_bridge_port():
    with veth_interface(VETH1, VETH1PEER):
        with bridges_with_port() as desired_state:
            assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
@pytest.mark.tier1
def test_add_veth_and_bring_both_up():
    with veth_interface_both_up(VETH1, VETH1PEER):
        c_state = statelib.show_only(
            (
                VETH1,
                VETH1PEER,
            )
        )
        assert c_state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
        assert c_state[Interface.KEY][1][Interface.STATE] == InterfaceState.UP


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
@pytest.mark.tier1
def test_modify_veth_peer():
    with veth_interface(VETH1, VETH1PEER) as d_state:
        d_state[Interface.KEY][0][Veth.CONFIG_SUBTREE][Veth.PEER] = VETH2PEER
        libnmstate.apply(d_state)

        c_state = statelib.show_only(
            (
                VETH1,
                VETH2PEER,
            )
        )
        assert (
            c_state[Interface.KEY][0][Veth.CONFIG_SUBTREE][Veth.PEER]
            == VETH2PEER
        )
        assert c_state[Interface.KEY][1][Interface.NAME] == VETH2PEER


@contextmanager
def bridges_with_port():
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: "ovs-br0",
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                Bridge.CONFIG_SUBTREE: {
                    Bridge.PORT_SUBTREE: [
                        {Bridge.Port.NAME: VETH1},
                    ]
                },
            },
            {
                Interface.NAME: "br0",
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                Bridge.CONFIG_SUBTREE: {
                    Bridge.PORT_SUBTREE: [
                        {
                            Bridge.Port.NAME: VETH1PEER,
                        },
                    ]
                },
            },
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)


@contextmanager
def veth_interface_both_up(ifname, peer):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: Veth.TYPE,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: peer,
                },
            },
            {
                Interface.NAME: peer,
                Interface.TYPE: Veth.TYPE,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: ifname,
                },
            },
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)


@contextmanager
def veth_interface(ifname, peer):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: Veth.TYPE,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: peer,
                },
            }
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY].append(
            {
                Interface.NAME: VETH1PEER,
                Interface.TYPE: InterfaceType.VETH,
                Interface.STATE: InterfaceState.ABSENT,
            }
        )
        libnmstate.apply(d_state)
