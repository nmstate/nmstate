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

# This file will hold the common code shared by linux bridge and ovs bridge.

from operator import itemgetter

from libnmstate.schema import Bridge

from ..state import merge_dict
from .base_iface import BaseIface


class BridgeIface(BaseIface):
    BRPORT_OPTIONS_METADATA = "_brport_options"

    @property
    def is_controller(self):
        return True

    @property
    def is_virtual(self):
        return True

    def sort_port(self):
        if self.port:
            self.raw[Bridge.CONFIG_SUBTREE][Bridge.PORT_SUBTREE].sort(
                key=itemgetter(Bridge.Port.NAME)
            )

    @property
    def _bridge_config(self):
        return self.raw.get(Bridge.CONFIG_SUBTREE, {})

    @property
    def port_configs(self):
        return self._bridge_config.get(Bridge.PORT_SUBTREE, [])

    def merge(self, other):
        super().merge(other)
        self._merge_bridge_ports(other)

    def _merge_bridge_ports(self, other):
        """
        Given a bridge desired state, and it's current state, merges
        those together.

        This extension of the interface merging mechanism simplifies the user's
        life in scenarios where the user wants to partially update the bridge's
        configuration - e.g. update only the bridge's port STP configuration -
        since it enables the user to simply specify the updated values rather
        than the full current state + the updated value.
        """
        if self._bridge_config.get(Bridge.PORT_SUBTREE) == []:
            # User explictly defined empty list for ports and expecting
            # removal of all ports.
            return

        other_indexed_ports = _index_port_configs(other.port_configs)
        self_indexed_ports = _index_port_configs(self.port_configs)

        # When defined, user need to specify the whole list of ports.
        for port_iface_name in (
            other_indexed_ports.keys() & self_indexed_ports.keys()
        ):
            merge_dict(
                self_indexed_ports[port_iface_name],
                other_indexed_ports[port_iface_name],
            )
        self.raw[Bridge.CONFIG_SUBTREE][Bridge.PORT_SUBTREE] = list(
            self_indexed_ports.values()
        )

    def pre_edit_validation_and_cleanup(self):
        if self.is_up:
            self.sort_port()
        super().pre_edit_validation_and_cleanup()

    def config_changed_port(self, cur_iface):
        changed_port = []
        cur_indexed_ports = _index_port_configs(cur_iface.port_configs)
        for port_config in self.port_configs:
            port_name = port_config[Bridge.Port.NAME]
            cur_port_config = cur_indexed_ports.get(port_name)
            if cur_port_config != port_config:
                changed_port.append(port_name)
        return changed_port


def _index_port_configs(port_configs):
    return {port[Bridge.Port.NAME]: port for port in port_configs}
