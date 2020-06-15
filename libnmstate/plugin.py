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

from abc import ABCMeta
from abc import abstractproperty
from abc import abstractmethod

from .error import NmstatePluginError


class NmstatePlugin(metaclass=ABCMeta):
    OVS_CAPABILITY = "openvswitch"
    TEAM_CAPABILITY = "team"

    PLUGIN_CAPABILITY_IFACE = "interface"
    PLUGIN_CAPABILITY_ROUTE = "route"
    PLUGIN_CAPABILITY_ROUTE_RULE = "route_rule"
    PLUGIN_CAPABILITY_DNS = "dns"

    DEFAULT_PRIORITY = 10

    def unload(self):
        pass

    @property
    def checkpoint(self):
        return None

    def refresh_content(self):
        pass

    @abstractproperty
    def name(self):
        pass

    @property
    def priority(self):
        return NmstatePlugin.DEFAULT_PRIORITY

    def get_interfaces(self):
        raise NmstatePluginError(
            f"Plugin {self.name} BUG: get_interfaces() not implemented"
        )

    def apply_changes(self, net_state, save_to_disk):
        pass

    @property
    def capabilities(self):
        return []

    @abstractmethod
    def plugin_capabilities(self):
        pass

    def create_checkpoint(self, timeout):
        return None

    def rollback_checkpoint(self, checkpoint=None):
        pass

    def destroy_checkpoint(self, checkpoint=None):
        pass

    def get_routes(self):
        raise NmstatePluginError(
            f"Plugin {self.name} BUG: get_routes() not implemented"
        )

    def get_route_rules(self):
        raise NmstatePluginError(
            f"Plugin {self.name} BUG: get_route_rules() not implemented"
        )

    def get_dns_client_config(self):
        raise NmstatePluginError(
            f"Plugin {self.name} BUG: get_dns_client_config() not implemented"
        )
