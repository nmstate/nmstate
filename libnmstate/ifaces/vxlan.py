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

from libnmstate.error import NmstateValueError
from libnmstate.schema import VXLAN

from .base_iface import BaseIface


class VxlanIface(BaseIface):
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
    def is_virtual(self):
        return True

    @property
    def can_have_ip_when_enslaved(self):
        return True

    def pre_edit_validation_and_cleanup(self):
        self._validate_mandatory_properties()
        super().pre_edit_validation_and_cleanup()

    def _validate_mandatory_properties(self):
        if self.is_up:
            for prop in (VXLAN.ID, VXLAN.BASE_IFACE, VXLAN.REMOTE):
                if prop not in self._vxlan_config:
                    raise NmstateValueError(
                        f"Vxlan tunnel {self.name} has missing mandatory "
                        f"property: {prop}"
                    )
