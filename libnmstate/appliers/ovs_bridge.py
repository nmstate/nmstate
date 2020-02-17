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
    bridge = iface_state.get(OVSBridge.CONFIG_SUBTREE, {})
    ports = bridge.get(OVSBridge.PORT_SUBTREE)
    if ports is None:
        return default
    return [p[OVSBridge.Port.NAME] for p in ports]


def set_ovs_bridge_ports_metadata(master_state, slave_state):
    bridge = master_state.get(OVSBridge.CONFIG_SUBTREE, {})
    ports = bridge.get(OVSBridge.PORT_SUBTREE, [])
    slave_name = slave_state[Interface.NAME]
    port = next(
        filter(lambda n: n[OVSBridge.Port.NAME] == slave_name, ports,), {},
    )
    slave_state[BRPORT_OPTIONS] = port
