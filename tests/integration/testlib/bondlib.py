# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType


@contextmanager
def bond_interface(name, port, extra_iface_state=None, create=True):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.BOND,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.PORT: port,
                },
            }
        ]
    }
    if extra_iface_state:
        desired_state[Interface.KEY][0].update(extra_iface_state)
        if port:
            desired_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.PORT
            ] = port

    if create:
        libnmstate.apply(desired_state)

    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: name,
                        Interface.TYPE: InterfaceType.BOND,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
        )
