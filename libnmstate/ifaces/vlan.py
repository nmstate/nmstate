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

from libnmstate.error import NmstateValueError
from libnmstate.schema import VLAN
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_string

from .base_iface import BaseIface


class VlanIface(BaseIface):
    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._vlan_id_changed = False

    @property
    def parent(self):
        return self._vlan_config.get(VLAN.BASE_IFACE)

    @property
    def need_parent(self):
        return True

    @property
    def _vlan_config(self):
        return self.raw.get(VLAN.CONFIG_SUBTREE, {})

    @property
    def vlan_id(self):
        return self._vlan_config.get(VLAN.ID)

    @property
    def base_iface(self):
        return self._vlan_config.get(VLAN.BASE_IFACE)

    @property
    def is_vlan_id_changed(self):
        return self._vlan_id_changed

    @property
    def is_virtual(self):
        return True

    @property
    def can_have_ip_as_port(self):
        return False

    def pre_edit_validation_and_cleanup(self):
        self._validate_vlan_properties()
        if self.is_up:
            self._validate_mandatory_properties()
        super().pre_edit_validation_and_cleanup()

    def _validate_vlan_properties(self):
        validate_string(self.base_iface, VLAN.BASE_IFACE)
        validate_integer(self.vlan_id, VLAN.ID, minimum=0, maximum=4095)

    def _validate_mandatory_properties(self):
        for prop in (VLAN.ID, VLAN.BASE_IFACE):
            if prop not in self._vlan_config:
                raise NmstateValueError(
                    f"VLAN tunnel {self.name} has missing mandatory "
                    f"property: {prop}"
                )

    def _mark_vlan_id_changed(self, ifaces):
        if self.is_up:
            cur_iface = ifaces.get_cur_iface(self.name, self.type)
            if cur_iface and self.vlan_id != cur_iface.vlan_id:
                self._vlan_id_changed = True

    def gen_metadata(self, ifaces):
        self._mark_vlan_id_changed(ifaces)
        super().gen_metadata(ifaces)
