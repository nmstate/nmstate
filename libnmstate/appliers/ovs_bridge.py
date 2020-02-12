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

from libnmstate.schema import Interface
from libnmstate.schema import OVSBridge


BRPORT_OPTIONS = "_brport_options"


def get_ovs_slaves_from_state(iface_state, default=()):
    slaves = []
    bridge = iface_state.get(OVSBridge.CONFIG_SUBTREE, {})
    ports = bridge.get(OVSBridge.PORT_SUBTREE)
    if ports is None:
        return default
    for port in ports:
        lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
        if lag:
            lag_slaves = lag.get(OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE)
            if lag_slaves:
                name_key = OVSBridge.Port.LinkAggregation.Slave.NAME
                slaves += [s[name_key] for s in lag_slaves]
        else:
            slaves.append(port[OVSBridge.Port.NAME])
    return slaves


def set_ovs_bridge_ports_metadata(master_state, slave_state):
    bridge = master_state.get(OVSBridge.CONFIG_SUBTREE, {})
    ports = bridge.get(OVSBridge.PORT_SUBTREE, [])
    slave_name = slave_state[Interface.NAME]

    port = _lookup_ovs_port_by_interface(ports, slave_name)

    slave_state[BRPORT_OPTIONS] = port


def _lookup_ovs_port_by_interface(ports, slave_name):
    for port in ports:
        lag_state = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
        if lag_state and _is_ovs_lag_slave(lag_state, slave_name):
            return port
        elif port[OVSBridge.Port.NAME] == slave_name:
            return port
    return {}


def _is_ovs_lag_slave(lag_state, iface_name):
    slaves = lag_state.get(OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE, ())
    for slave in slaves:
        if slave[OVSBridge.Port.LinkAggregation.Slave.NAME] == iface_name:
            return True
    return False
