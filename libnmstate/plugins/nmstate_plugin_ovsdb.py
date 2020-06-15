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

from libnmstate.plugin import NmstatePlugin


class NmstateOvsdbPlugin(NmstatePlugin):
    @property
    def name(self):
        return "nmstate-plugin-ovsdb"

    @property
    def priority(self):
        return NmstatePlugin.DEFAULT_PRIORITY + 1

    @property
    def plugin_capabilities(self):
        return NmstatePlugin.PLUGIN_CAPABILITY_IFACE

    def get_interfaces(self):
        return []


NMSTATE_PLUGIN = NmstateOvsdbPlugin
