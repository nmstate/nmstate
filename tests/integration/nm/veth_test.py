# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Veth

from ..testlib.env import nm_major_minor_version
from ..testlib import cmdlib
from ..testlib.veth import veth_interface


VETH1 = "veth1"
VETH1PEER = "veth1peer"
VETH1PEER2 = "veth1ep"


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
def test_remove_peer_connection():
    with veth_interface(VETH1, VETH1PEER) as desired_state:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)
        assert (
            cmdlib.exec_cmd(f"nmcli connection show {VETH1PEER}".split())[0]
            != 0
        )


@pytest.fixture
def veth1_with_ignored_peer():
    cmdlib.exec_cmd(
        f"ip link add {VETH1} type veth peer {VETH1PEER}".split(), check=True
    )
    cmdlib.exec_cmd(f"ip link set {VETH1} up".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {VETH1PEER} up".split(), check=True)
    cmdlib.exec_cmd(f"nmcli d set {VETH1} managed true".split(), check=True)
    cmdlib.exec_cmd(
        f"nmcli d set {VETH1PEER} managed false".split(), check=True
    )
    yield
    cmdlib.exec_cmd(f"ip link del {VETH1}".split())
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: VETH1PEER,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
def test_veth_with_ignored_peer(veth1_with_ignored_peer):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: VETH1,
                Interface.TYPE: InterfaceType.VETH,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: VETH1PEER,
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    assert (
        "unmanaged"
        in cmdlib.exec_cmd(
            f"nmcli -g GENERAL.STATE d show {VETH1PEER}".split()
        )[1]
    )


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth interfaces is not supported on NetworkManager.",
)
def test_veth_with_ignored_peer_changed_to_new_peer(veth1_with_ignored_peer):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: VETH1,
                Interface.TYPE: InterfaceType.VETH,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: VETH1PEER2,
                },
            }
        ]
    }
    with pytest.raises(NmstateValueError):
        libnmstate.apply(desired_state)


def test_veth_rename_peer():
    with veth_interface(VETH1, VETH1PEER) as desired_state:
        desired_state[Interface.KEY][0][Veth.CONFIG_SUBTREE][
            Veth.PEER
        ] = "anotherpeer"
        libnmstate.apply(desired_state)
        assert (
            "connected"
            in cmdlib.exec_cmd(
                f"nmcli -g GENERAL.STATE d show {VETH1}".split()
            )[1]
        )
        assert (
            "connected"
            in cmdlib.exec_cmd(
                "nmcli -g GENERAL.STATE d show anotherpeer".split()
            )[1]
        )
