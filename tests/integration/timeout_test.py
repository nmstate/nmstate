# SPDX-License-Identifier: LGPL-2.1-or-later
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
