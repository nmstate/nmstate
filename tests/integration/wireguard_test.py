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


import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Wireguard

from .testlib import assertlib
from .testlib import cmdlib


WG0 = "wg0"
WG0_PRIVATE_KEY = "eBampleZp5x87cNoRJaHdAOzxrxDfDUn7pGmrY/Am3I="
WG1_PRIVATE_KEY = "otherkeyp5x87cNoRJaHdAOzxrxDfDUn7pGmrY/AmzI="
PEER0_PRESHARED_KEY = "exampleABe4wWyz4jh+uwX7vqRpNeGEtgAnUbwNjEug="
PEER0_PUBLIC_KEY = "2Gl0SATbfrrzxfrSkhNoRR9Jg56y533y07KtIVngAk0="


def test_add_and_remove_wireguard():
    with wireguard_interface(WG0) as desired_state:
        assertlib.assert_state(desired_state)

        _, out, _ = cmdlib.exec_cmd(f"wg showconf {WG0}".split(), check=True)
        assert WG0_PRIVATE_KEY in out

    assertlib.assert_absent(WG0)


def test_modify_wireguard():
    with wireguard_interface(WG0) as desired_state:
        wg_state = desired_state[Interface.KEY][0][Wireguard.CONFIG_SUBTREE]
        wg_state[Wireguard.PRIVATE_KEY] = WG1_PRIVATE_KEY
        wg_state[Wireguard.LISTEN_PORT] = 9500

        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)

        _, out, _ = cmdlib.exec_cmd(f"wg showconf {WG0}".split(), check=True)
        assert WG1_PRIVATE_KEY in out
        assert str(9500) in out


def test_add_and_remove_wireguard_with_peer():
    with wireguard_interface_with_peer(WG0) as desired_state:
        assertlib.assert_state_match(desired_state)

        _, out, _ = cmdlib.exec_cmd(f"wg showconf {WG0}".split(), check=True)
        assert PEER0_PRESHARED_KEY in out
        assert PEER0_PUBLIC_KEY in out

    assertlib.assert_absent(WG0)


def test_add_peer_to_wireguard():
    with wireguard_interface(WG0) as desired_state:
        wg_state = desired_state[Interface.KEY][0][Wireguard.CONFIG_SUBTREE]
        wg_state[Wireguard.Peer.CONFIG_SUBTREE] = [
            {
                Wireguard.Peer.ALLOWED_IPS: ["192.0.2.1"],
                Wireguard.Peer.ENDPOINT: "my-wg.example.com:4001",
                Wireguard.Peer.PRESHARED_KEY: PEER0_PRESHARED_KEY,
                Wireguard.Peer.PUBLIC_KEY: PEER0_PUBLIC_KEY,
            },
        ]
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

        _, out, _ = cmdlib.exec_cmd(f"wg showconf {WG0}".split(), check=True)
        assert PEER0_PRESHARED_KEY in out
        assert PEER0_PUBLIC_KEY in out


def test_remove_wireguard_peer():
    with wireguard_interface_with_peer(WG0) as desired_state:
        wg_state = desired_state[Interface.KEY][0][Wireguard.CONFIG_SUBTREE]
        wg_state[Wireguard.Peer.CONFIG_SUBTREE] = []
        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)

        _, out, _ = cmdlib.exec_cmd(f"wg showconf {WG0}".split(), check=True)
        assert PEER0_PRESHARED_KEY not in out
        assert PEER0_PUBLIC_KEY not in out

    assertlib.assert_absent(WG0)


@contextmanager
def wireguard_interface_with_peer(ifname):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.WIREGUARD,
                Interface.STATE: InterfaceState.UP,
                Wireguard.CONFIG_SUBTREE: {
                    Wireguard.LISTEN_PORT: 9000,
                    Wireguard.PRIVATE_KEY: WG0_PRIVATE_KEY,
                    Wireguard.Peer.CONFIG_SUBTREE: [
                        {
                            Wireguard.Peer.ALLOWED_IPS: ["192.0.2.1"],
                            Wireguard.Peer.ENDPOINT: "my-wg.example.com:4001",
                            Wireguard.Peer.PRESHARED_KEY: PEER0_PRESHARED_KEY,
                            Wireguard.Peer.PUBLIC_KEY: PEER0_PUBLIC_KEY,
                        },
                    ],
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


@contextmanager
def wireguard_interface(ifname):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.WIREGUARD,
                Interface.STATE: InterfaceState.UP,
                Wireguard.CONFIG_SUBTREE: {
                    Wireguard.LISTEN_PORT: 9000,
                    Wireguard.PRIVATE_KEY: WG0_PRIVATE_KEY,
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
