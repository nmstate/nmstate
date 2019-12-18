#
# Copyright (c) 2019-2020 Red Hat, Inc.
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
import copy

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge


class Bridge:
    def __init__(self, name):
        self._name = name
        self._ifaces = [
            {
                Interface.NAME: name,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                OVSBridge.CONFIG_SUBTREE: {},
            }
        ]
        self._bridge_iface = self._ifaces[0]

    def set_options(self, options):
        self._bridge_iface[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.OPTIONS_SUBTREE
        ] = options

    def add_system_port(self, name):
        self._add_port(name)

    def add_link_aggregation_port(self, name, slaves, mode=None):
        self._add_port(name)
        port = self._get_port(name)
        port[OVSBridge.Port.LINK_AGGREGATION_SUBTREE] = {
            OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE: [
                {OVSBridge.Port.LinkAggregation.Slave.NAME: slave}
                for slave in slaves
            ]
        }
        if mode:
            port[OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
                OVSBridge.Port.LinkAggregation.MODE
            ] = mode

    def add_internal_port(self, name, *, mac=None, ipv4_state=None):
        ifstate = {
            Interface.NAME: name,
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
        }
        if mac:
            ifstate[Interface.MAC] = mac
        if ipv4_state:
            ifstate[Interface.IPV4] = ipv4_state

        self._add_port(name)
        self._ifaces.append(ifstate)

    def _add_port(self, name):
        self._bridge_iface[OVSBridge.CONFIG_SUBTREE].setdefault(
            OVSBridge.PORT_SUBTREE, []
        ).append({OVSBridge.Port.NAME: name})

    def _get_port(self, name):
        ports = self._bridge_iface[OVSBridge.CONFIG_SUBTREE].get(
            OVSBridge.PORT_SUBTREE, []
        )
        return next(
            (port for port in ports if port[OVSBridge.Port.NAME] == name), None
        )

    def del_port(self, name):
        new_ports = [
            port
            for port in self._bridge_iface[OVSBridge.CONFIG_SUBTREE][
                OVSBridge.PORT_SUBTREE
            ]
            if port[OVSBridge.Port.NAME] != name
        ]
        self._bridge_iface[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] = new_ports

    @contextmanager
    def create(self):
        desired_state = {
            Interface.KEY: _set_ifaces_state(self._ifaces, InterfaceState.UP)
        }
        libnmstate.apply(desired_state)
        try:
            yield desired_state
        finally:
            desired_state = {
                Interface.KEY: _set_ifaces_state(
                    self._ifaces, InterfaceState.ABSENT
                )
            }
            libnmstate.apply(desired_state, verify_change=False)


def _set_ifaces_state(ifaces, state):
    ifaces = copy.deepcopy(ifaces)
    for iface in ifaces:
        iface[Interface.STATE] = state
    return ifaces
