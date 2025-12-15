# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge
from libnmstate.schema import VLAN


@pytest.mark.tier1
@pytest.mark.slow
def test_lot_of_vlans_with_bridges(eth1_up):
    interfaces = []
    for i in range(100, 600):
        interfaces.extend(
            [
                {
                    Interface.NAME: "vlan." + str(i),
                    Interface.TYPE: InterfaceType.VLAN,
                    Interface.STATE: InterfaceState.UP,
                    VLAN.CONFIG_SUBTREE: {VLAN.BASE_IFACE: "eth1", VLAN.ID: i},
                },
                {
                    Interface.NAME: "linux-br" + str(i),
                    Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                    Interface.STATE: InterfaceState.UP,
                    LinuxBridge.CONFIG_SUBTREE: {
                        LinuxBridge.PORT_SUBTREE: [
                            {LinuxBridge.Port.NAME: "vlan." + str(i)}
                        ]
                    },
                },
            ]
        )
    try:
        libnmstate.apply({Interface.KEY: interfaces})
    finally:
        for iface in interfaces:
            iface[Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply({Interface.KEY: interfaces})
