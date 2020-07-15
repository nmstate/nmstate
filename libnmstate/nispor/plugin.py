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


class NisporPlugin(NmstatePlugin):
    @property
    def name(self):
        return "nispor"

    @property
    def plugin_capabilities(self):
        return [
            NmstatePlugin.PLUGIN_CAPABILITY_IFACE,
        ]

    def get_interfaces(self):
        np_state = json.loads(nispor.get_state())
        ifaces = []
        for np_iface in np_state.get("ifaces", {}).values():
            np_iface_type = np_iface["iface_type"]
            if np_iface["state"] != "Unknown":
                if np_iface_type in ["Unknown", "Veth"]:
                    ifaces.append(NisporBaseIface(np_iface).to_dict())
        return ifaces
