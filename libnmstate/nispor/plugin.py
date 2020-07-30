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

import json

import nispor

from libnmstate.plugin import NmstatePlugin

from .base_iface import NisporBaseIface
from .dummy import NisporDummyIface
from .ethernet import NisporEthernetIface
from .bond import NisporBondIface
from .vlan import NisporVlanIface
from .linux_bridge import NisporLinuxBridgeIface


class NisporPlugin(NmstatePlugin):
    @property
    def name(self):
        return "nispor"

    @property
    def plugin_capabilities(self):
        return [
            NmstatePlugin.PLUGIN_CAPABILITY_IFACE,
        ]

    @property
    def priority(self):
        # Let NetworkManagerPlugin take priority as nispor might be wrong on
        # DHCP status and currently nispor does not support all interface types
        # yet.
        return NmstatePlugin.DEFAULT_PRIORITY - 1

    def get_interfaces(self):
        np_state = json.loads(nispor.get_state())
        ifaces = []
        for np_iface in np_state.get("ifaces", {}).values():
            iface_type = np_iface["iface_type"]
            if iface_type in ("Dummy", {"Other": "Dummy"}):
                ifaces.append(NisporDummyIface(np_iface).to_dict())
            elif iface_type == "Veth":
                ifaces.append(NisporEthernetIface(np_iface).to_dict())
            elif iface_type == "Bond":
                ifaces.append(NisporBondIface(np_iface).to_dict())
            elif iface_type == "Vlan":
                ifaces.append(NisporVlanIface(np_iface).to_dict())
            elif iface_type == "Bridge":
                ifaces.append(NisporLinuxBridgeIface(np_iface).to_dict())
            else:
                ifaces.append(NisporBaseIface(np_iface).to_dict())
        return ifaces
