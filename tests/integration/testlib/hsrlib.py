# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Hsr
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType


@contextmanager
def hsr_interface(
    name, port1, port2, mcast_spec=40, protocol="prp", create=True
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.HSR,
                Interface.STATE: InterfaceState.UP,
                Hsr.CONFIG_SUBTREE: {
                    Hsr.PORT1: port1,
                    Hsr.PORT2: port2,
                    Hsr.MULTICAST_SPEC: mcast_spec,
                    Hsr.PROTOCOL: protocol,
                },
            }
        ]
    }

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
                        Interface.TYPE: InterfaceType.HSR,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
        )
