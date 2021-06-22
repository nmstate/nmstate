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
        """
        Return a list of dict with network interface running status with
        mix of running status and running configure.
        """
        raise NmstatePluginError(
            f"Plugin {self.name} BUG: get_interfaces() not implemented"
        )

    def get_running_config_interfaces(self):
        """
        Return a list of dict with network interface running configuration.
        Notes:
            * the IP/DHCP/Route retrieved from DHCP/Autoconf are not running
              configuration.
        """
        return []

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

    def get_global_state(self):
        """
        Allowing plugin to append global information to content of
        `libnmstate.show()`.
        """
        return {}

    @property
    def is_supplemental_only(self):
        """
        Return True when plugin can only append information to
        interfaces reported by other plugin.
        Retrun False when plugin can report new interface.
        """
        return False

    def generate_configurations(self, net_state):
        """
        Returning a list of strings for configurations which could be save
        persistently.
        """
        return []

    def get_ignored_kernel_interface_names(self):
        """
        Return a list of kernel interface names which should be ignored
        during verification stage.
        """
        return []
