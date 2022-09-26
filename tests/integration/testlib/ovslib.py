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
from libnmstate.schema import OVSInterface


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

    def set_ovs_db(self, ovs_db_config):
        self._bridge_iface[OVSBridge.OVS_DB_SUBTREE] = ovs_db_config

    def add_system_port(self, name):
        self._add_port(name)

    def add_link_aggregation_port(self, name, port, mode=None):
        self._add_port(name)
        port_cfg = self._get_port(name)
        port_cfg[OVSBridge.Port.LINK_AGGREGATION_SUBTREE] = {
            OVSBridge.Port.LinkAggregation.PORT_SUBTREE: [
                {OVSBridge.Port.LinkAggregation.Port.NAME: port_member}
                for port_member in port
            ]
        }
        if mode:
            port[OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
                OVSBridge.Port.LinkAggregation.MODE
            ] = mode

    def add_internal_port(
        self,
        name,
        *,
        mac=None,
        copy_mac_from=None,
        ipv4_state=None,
        ovs_db=None,
        patch_state=None,
        mtu=None,
        dpdk_state=None,
    ):
        ifstate = {
            Interface.NAME: name,
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
        }
        if mac:
            ifstate[Interface.MAC] = mac
        if copy_mac_from:
            ifstate[Interface.COPY_MAC_FROM] = copy_mac_from
        if mtu:
            ifstate[Interface.MTU] = mtu
        if ipv4_state:
            ifstate[Interface.IPV4] = ipv4_state
        if ovs_db:
            ifstate[OVSInterface.OVS_DB_SUBTREE] = ovs_db
        if patch_state:
            ifstate[OVSInterface.PATCH_CONFIG_SUBTREE] = patch_state
        if dpdk_state:
            ifstate[OVSInterface.DPDK_CONFIG_SUBTREE] = dpdk_state

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


@contextmanager
def ovs_bridge(br_name, sys_port_names, internal_port_name):
    bridge = Bridge(br_name)
    bridge.add_internal_port(internal_port_name)
    for sys_port_name in sys_port_names:
        bridge.add_system_port(sys_port_name)
    with bridge.create():
        yield bridge.state


@contextmanager
# The bond_ports should be in the format of
#   dict(bond_port_name, bond_sys_port_names)
def ovs_bridge_bond(br_name, bond_ports, internal_port_name):
    bridge = Bridge(br_name)
    bridge.add_internal_port(internal_port_name)
    for bond_port_name, bond_sys_port_names in bond_ports.items():
        bridge.add_link_aggregation_port(bond_port_name, bond_sys_port_names)
    with bridge.create():
        yield bridge.state
