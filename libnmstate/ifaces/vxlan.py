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
from libnmstate.schema import VXLAN
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_string

from .base_iface import BaseIface


class VxlanIface(BaseIface):
    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._vxlan_id_changed = False

    @property
    def parent(self):
        return self._vxlan_config.get(VXLAN.BASE_IFACE)

    @property
    def need_parent(self):
        return True

    @property
    def _vxlan_config(self):
        return self.raw.get(VXLAN.CONFIG_SUBTREE, {})

    @property
    def vxlan_id(self):
        return self._vxlan_config.get(VXLAN.ID)

    @property
    def base_iface(self):
        return self._vxlan_config.get(VXLAN.BASE_IFACE)

    @property
    def remote(self):
        return self._vxlan_config.get(VXLAN.REMOTE)

    @property
    def destination_port(self):
        return self._vxlan_config.get(VXLAN.DESTINATION_PORT)

    @property
    def is_vxlan_id_changed(self):
        return self._vxlan_id_changed

    @property
    def is_virtual(self):
        return True

    @property
    def can_have_ip_as_port(self):
        return False

    def _mark_vxlan_id_changed(self, ifaces):
        if self.is_up:
            cur_iface = ifaces.get_cur_iface(self.name, self.type)
            if cur_iface and self.vxlan_id != cur_iface.vxlan_id:
                self._vxlan_id_changed = True

    def gen_metadata(self, ifaces):
        self._mark_vxlan_id_changed(ifaces)
        super().gen_metadata(ifaces)

    def pre_edit_validation_and_cleanup(self):
        self._validate_vxlan_properties()
        if self.is_up:
            self._validate_mandatory_properties()
        super().pre_edit_validation_and_cleanup()

    def _validate_vxlan_properties(self):
        validate_string(self.base_iface, VXLAN.BASE_IFACE)
        validate_integer(self.vxlan_id, VXLAN.ID, minimum=0, maximum=16777215)
        validate_string(self.remote, VXLAN.REMOTE)
        validate_integer(self.destination_port, VXLAN.DESTINATION_PORT)

    def _validate_mandatory_properties(self):
        for prop in (VXLAN.ID, VXLAN.BASE_IFACE, VXLAN.REMOTE):
            if prop not in self._vxlan_config:
                raise NmstateValueError(
                    f"Vxlan tunnel {self.name} has missing mandatory "
                    f"property: {prop}"
                )
