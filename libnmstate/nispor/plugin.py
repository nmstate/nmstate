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

from nispor import NisporNetState

from libnmstate.plugin import NmstatePlugin
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .base_iface import NisporPluginBaseIface
from .bond import NisporPluginBondIface
from .bridge import NisporPluginBridgeIface
from .dummy import NisporPluginDummyIface
from .ethernet import NisporPluginEthernetIface
from .macvlan import NisporPluginMacVlanIface
from .macvtap import NisporPluginMacVtapIface
from .vlan import NisporPluginVlanIface
from .vxlan import NisporPluginVxlanIface
from .route import nispor_route_state_to_nmstate
from .route_rule import nispor_route_rule_state_to_nmstate
from .vrf import NisporPluginVrfIface
from .ovs import NisporPluginOvsInternalIface


class NisporPlugin(NmstatePlugin):
    @property
    def name(self):
        return "nispor"

    @property
    def plugin_capabilities(self):
        return [
            NmstatePlugin.PLUGIN_CAPABILITY_IFACE,
            NmstatePlugin.PLUGIN_CAPABILITY_ROUTE,
            NmstatePlugin.PLUGIN_CAPABILITY_ROUTE_RULE,
        ]

    @property
    def priority(self):
        # Let NetworkManagerPlugin take priority as nispor might be wrong on
        # DHCP status and currently nispor does not support all interface types
        # yet.
        return NmstatePlugin.DEFAULT_PRIORITY - 1

    def get_interfaces(self):
        np_state = NisporNetState.retrieve()
        ifaces = []
        for np_iface in np_state.ifaces.values():
            iface_type = np_iface.type
            if iface_type == "dummy":
                ifaces.append(NisporPluginDummyIface(np_iface).to_dict())
            elif iface_type == "veth":
                ifaces.append(NisporPluginEthernetIface(np_iface).to_dict())
            elif iface_type == "ethernet":
                ifaces.append(NisporPluginEthernetIface(np_iface).to_dict())
            elif iface_type == "bond":
                ifaces.append(NisporPluginBondIface(np_iface).to_dict())
            elif iface_type == "vlan":
                ifaces.append(NisporPluginVlanIface(np_iface).to_dict())
            elif iface_type == "vxlan":
                ifaces.append(NisporPluginVxlanIface(np_iface).to_dict())
            elif iface_type == "mac_vlan":
                ifaces.append(NisporPluginMacVlanIface(np_iface).to_dict())
            elif iface_type == "mac_vtap":
                ifaces.append(NisporPluginMacVtapIface(np_iface).to_dict())
            elif iface_type == "bridge":
                np_ports = []
                for port_name in np_iface.ports:
                    if port_name in np_state.ifaces.keys():
                        np_ports.append(np_state.ifaces[port_name])
                ifaces.append(
                    NisporPluginBridgeIface(np_iface, np_ports).to_dict()
                )
            elif iface_type == "vrf":
                ifaces.append(NisporPluginVrfIface(np_iface).to_dict())
            elif iface_type == "openv_switch":
                ifaces.append(NisporPluginOvsInternalIface(np_iface).to_dict())
            else:
                ifaces.append(NisporPluginBaseIface(np_iface).to_dict())
        return ifaces

    def get_routes(self):
        np_state = NisporNetState.retrieve()
        return {Route.RUNNING: nispor_route_state_to_nmstate(np_state.routes)}

    def get_route_rules(self):
        np_state = NisporNetState.retrieve()
        return {
            RouteRule.CONFIG: nispor_route_rule_state_to_nmstate(
                np_state.route_rules
            )
        }
