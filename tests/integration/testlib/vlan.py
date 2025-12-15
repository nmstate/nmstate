# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import VLAN


@contextmanager
def vlan_interface(ifname, vlan_id, base_iface, protocol=None):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.TYPE: {VLAN.ID: vlan_id, VLAN.BASE_IFACE: base_iface},
            }
        ]
    }
    if protocol:
        desired_state[Interface.KEY][0][VLAN.CONFIG_SUBTREE][
            VLAN.PROTOCOL
        ] = protocol
    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ifname,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )
