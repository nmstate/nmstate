# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Veth

from .cmdlib import exec_cmd


def create_veth_pair(nic, nic_peer, peer_ns):
    """
    Create a veth pair and place the {peer} into {peer_ns} namespace.
    The {nic} will be marked as managed by NetworkManager
    """
    exec_cmd(
        f"ip link add {nic} type veth peer name {nic_peer}".split(),
        check=True,
    )
    # namespace might already exist
    exec_cmd(f"ip netns add {peer_ns}".split(), check=False)
    exec_cmd(f"ip link set {nic_peer} netns {peer_ns}".split(), check=True)
    exec_cmd(f"ip link set {nic} up".split(), check=True)
    exec_cmd(
        f"ip netns exec {peer_ns} ip link set {nic_peer} up".split(),
        check=True,
    )
    exec_cmd(f"nmcli device set {nic} managed yes".split(), check=True)


def remove_veth_pair(nic, peer_ns):
    exec_cmd(f"ip link del {nic}".split())
    exec_cmd(f"ip netns del {peer_ns}".split())
    # Use nmstate to ensure nic is deleted instead of using `ip link del`
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: nic,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@contextmanager
def veth_interface(ifname, peer, kernel_mode=False):
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
        libnmstate.apply(d_state, kernel_only=kernel_mode)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY].append(
            {
                Interface.NAME: peer,
                Interface.TYPE: InterfaceType.VETH,
                Interface.STATE: InterfaceState.ABSENT,
            }
        )
        libnmstate.apply(d_state, kernel_only=kernel_mode)
