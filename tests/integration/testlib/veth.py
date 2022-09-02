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
    exec_cmd(f"ip netns add {peer_ns}".split(), check=True)
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
        libnmstate.apply(d_state, kernel_only=kernel_mode, verify_change=False)
