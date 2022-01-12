#
# Copyright (c) 2020-2021 Red Hat, Inc.
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

import logging

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import VRF
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_list

from .base_iface import BaseIface


class VrfIface(BaseIface):
    TABLE_ID_CHANGED_METADATA = "_table_id_changed"

    def sort_port(self):
        if self.port:
            self.raw[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].sort()

    @property
    def route_table_id(self):
        return self.raw.get(VRF.CONFIG_SUBTREE, {}).get(VRF.ROUTE_TABLE_ID)

    @property
    def port(self):
        return self.raw.get(VRF.CONFIG_SUBTREE, {}).get(VRF.PORT_SUBTREE, [])

    @property
    def is_controller(self):
        return True

    @property
    def is_virtual(self):
        return True

    def pre_edit_validation_and_cleanup(self):
        self._validate_vrf_properties()
        super().pre_edit_validation_and_cleanup()
        if self.is_up and (self.is_desired or self.is_changed):
            self._validate_route_table_id()
            self._remove_mac_address()
            self._remove_accept_all_mac_addresses_false()

    def _validate_vrf_properties(self):
        validate_list(self.port, VRF.PORT_SUBTREE, elem_type=str)
        validate_integer(self.route_table_id, VRF.ROUTE_TABLE_ID)

    def _validate_route_table_id(self):
        """
        The route table ID is manadatory
        """
        if not self.raw.get(VRF.CONFIG_SUBTREE, {}).get(VRF.ROUTE_TABLE_ID):
            raise NmstateValueError(
                f"Invalid route table ID for VRF interface {self.name}"
            )

    def _remove_mac_address(self):
        if self.original_desire_dict.get(Interface.MAC):
            logging.warn(
                "Applying MAC address of VRF interface is not supported yet. "
                "Ignoring"
            )
        self.original_desire_dict.pop(Interface.MAC, None)
        self.raw.pop(Interface.MAC, None)

    def _remove_accept_all_mac_addresses_false(self):
        if (
            self.original_desire_dict.get(Interface.ACCEPT_ALL_MAC_ADDRESSES)
            is False
        ):
            self.original_desire_dict.pop(
                Interface.ACCEPT_ALL_MAC_ADDRESSES, None
            )
        if self.raw.get(Interface.ACCEPT_ALL_MAC_ADDRESSES) is False:
            self.raw.pop(Interface.ACCEPT_ALL_MAC_ADDRESSES, None)

    def remove_port(self, port_name):
        self.raw[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [
            s for s in self.port if s != port_name
        ]
        self.sort_port()
