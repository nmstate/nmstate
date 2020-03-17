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
import re

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge

from . import cmdlib


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

    @property
    def ports_names(self):
        return [port[OVSBridge.Port.NAME] for port in self._get_ports()]

    def _add_port(self, name):
        self._bridge_iface[OVSBridge.CONFIG_SUBTREE].setdefault(
            OVSBridge.PORT_SUBTREE, []
        ).append({OVSBridge.Port.NAME: name})

    def _get_port(self, name):
        ports = self._get_ports()
        return next(
            (port for port in ports if port[OVSBridge.Port.NAME] == name), None
        )

    def _get_ports(self):
        return self._bridge_iface[OVSBridge.CONFIG_SUBTREE].get(
            OVSBridge.PORT_SUBTREE, []
        )

    def set_port_option(self, port_name, new_option):
        for port_option in self._bridge_iface[OVSBridge.CONFIG_SUBTREE].get(
            OVSBridge.PORT_SUBTREE, []
        ):
            if port_option[OVSBridge.Port.NAME] == port_name:
                port_option.update(new_option)

    @contextmanager
    def create(self):
        desired_state = self.state
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

    def apply(self):
        libnmstate.apply(self.state)

    @property
    def state(self):
        return {
            Interface.KEY: _set_ifaces_state(self._ifaces, InterfaceState.UP)
        }


def _set_ifaces_state(ifaces, state):
    ifaces = copy.deepcopy(ifaces)
    for iface in ifaces:
        iface[Interface.STATE] = state
    return ifaces


def get_proxy_port_name_of_ovs_interface(iface_name):
    output = cmdlib.exec_cmd("ovs-vsctl show".split(" "), check=True)[1]
    port_name = None
    port_line_re = re.compile(r'^\s+Port\s"(.+)"$')
    iface_line_re = re.compile(rf'^\s+Interface\s"{iface_name}"$')
    for line in output.split("\n"):
        match = port_line_re.match(line)
        if match:
            port_name = match.groups()[0]
            continue
        if iface_line_re.match(line):
            return port_name
    return None
