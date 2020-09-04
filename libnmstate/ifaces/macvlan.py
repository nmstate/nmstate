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
from libnmstate.schema import MacVlan

from .base_iface import BaseIface


class MacVlanIface(BaseIface):
    @property
    def parent(self):
        return self._macvlan_config.get(MacVlan.BASE_IFACE)

    @property
    def need_parent(self):
        return True

    @property
    def _macvlan_config(self):
        return self.raw.get(MacVlan.CONFIG_SUBTREE, {})

    @property
    def is_virtual(self):
        return True

    @property
    def can_have_ip_when_enslaved(self):
        return False

    def pre_edit_validation_and_cleanup(self):
        self._validate_mode()
        self._validate_mandatory_properties()
        super().pre_edit_validation_and_cleanup()

    def _validate_mode(self):
        if self._macvlan_config.get(
            MacVlan.MODE
        ) != MacVlan.Mode.PASSTHRU and not self._macvlan_config.get(
            MacVlan.PROMISCUOUS
        ):
            raise NmstateValueError(
                "Disable promiscuous is only allowed on passthru mode"
            )
        if self._macvlan_config.get(MacVlan.MODE) == MacVlan.Mode.UNKNOWN:
            raise NmstateValueError(
                "Mode unknown is not supported when appying the state"
            )

    def _validate_mandatory_properties(self):
        if self.is_up:
            for prop in (MacVlan.MODE, MacVlan.BASE_IFACE):
                if prop not in self._macvlan_config:
                    raise NmstateValueError(
                        f"MacVlan tunnel {self.name} has missing mandatory "
                        f"property: {prop}"
                    )
