# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import libnmstate

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import VXLAN


class VxlanState:
    def __init__(
        self,
        id,
        base_if=None,
        local=None,
        remote=None,
        learning=True,
        destination_port=4789,
    ):
        self.name = f"{base_if}.{id}"
        self.id = id
        self.base_if = base_if
        self.learning = learning
        self.local = local
        self.remote = remote
        self.destination_port = destination_port

    @property
    def up(self):
        state = {
            Interface.NAME: self.name,
            Interface.TYPE: VXLAN.TYPE,
            Interface.STATE: InterfaceState.UP,
            VXLAN.CONFIG_SUBTREE: {
                VXLAN.ID: self.id,
                VXLAN.BASE_IFACE: self.base_if,
                VXLAN.LEARNING: self.learning,
                VXLAN.LOCAL: self.local,
                VXLAN.REMOTE: self.remote,
                VXLAN.DESTINATION_PORT: self.destination_port,
            },
        }
        if state[VXLAN.CONFIG_SUBTREE][VXLAN.BASE_IFACE] is None:
            del state[VXLAN.CONFIG_SUBTREE][VXLAN.BASE_IFACE]
        if state[VXLAN.CONFIG_SUBTREE][VXLAN.LOCAL] is None:
            del state[VXLAN.CONFIG_SUBTREE][VXLAN.LOCAL]
        if state[VXLAN.CONFIG_SUBTREE][VXLAN.REMOTE] is None:
            del state[VXLAN.CONFIG_SUBTREE][VXLAN.REMOTE]
        return state

    @property
    def absent(self):
        return {
            Interface.NAME: self.name,
            Interface.TYPE: VXLAN.TYPE,
            Interface.STATE: InterfaceState.ABSENT,
        }

    @property
    def down(self):
        return {
            Interface.NAME: self.name,
            Interface.TYPE: VXLAN.TYPE,
            Interface.STATE: InterfaceState.DOWN,
        }


@contextmanager
def vxlan_interfaces(*vxlans, create=True):
    setup_state = vxlans_up(vxlans)
    if create:
        libnmstate.apply(setup_state)
    try:
        yield setup_state
    finally:
        libnmstate.apply(vxlans_absent(vxlans))


def vxlans_up(vxlans):
    vxlans_state = [vxlan_state.up for vxlan_state in vxlans]
    return {Interface.KEY: vxlans_state}


def vxlans_absent(vxlans):
    vxlans_state = [vxlan_state.absent for vxlan_state in vxlans]
    return {Interface.KEY: vxlans_state}


def vxlans_down(vxlans):
    vxlans_state = [vxlan_state.down for vxlan_state in vxlans]
    return {Interface.KEY: vxlans_state}
