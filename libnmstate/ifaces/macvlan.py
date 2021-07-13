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
from libnmstate.validator import validate_boolean
from libnmstate.validator import validate_string

from .base_iface import BaseIface


VALID_MODES = [
    MacVlan.Mode.UNKNOWN,
    MacVlan.Mode.VEPA,
    MacVlan.Mode.BRIDGE,
    MacVlan.Mode.PRIVATE,
    MacVlan.Mode.PASSTHRU,
    MacVlan.Mode.SOURCE,
]


class MacVlanIface(BaseIface):
    @property
    def parent(self):
        return self.config_subtree.get(MacVlan.BASE_IFACE)

    @property
    def need_parent(self):
        return True

    @property
    def config_subtree(self):
        return self.raw.get(MacVlan.CONFIG_SUBTREE, {})

    @property
    def is_virtual(self):
        return True

    @property
    def can_have_ip_when_enslaved(self):
        return False

    @property
    def mode(self):
        return self.config_subtree.get(MacVlan.MODE)

    @property
    def base_iface(self):
        return self.config_subtree.get(MacVlan.BASE_IFACE)

    @property
    def promiscuous(self):
        return self.config_subtree.get(MacVlan.PROMISCUOUS)

    def pre_edit_validation_and_cleanup(self):
        self._validate_macvlan_properties()
        if self.is_up:
            self._validate_mode()
            self._validate_mandatory_properties()
        super().pre_edit_validation_and_cleanup()

    def _validate_macvlan_properties(self):
        validate_string(self.base_iface, MacVlan.BASE_IFACE)
        validate_string(self.mode, MacVlan.MODE, VALID_MODES)
        validate_boolean(self.promiscuous, MacVlan.PROMISCUOUS)

    def _validate_mode(self):
        if self.config_subtree.get(
            MacVlan.MODE
        ) != MacVlan.Mode.PASSTHRU and not self.config_subtree.get(
            MacVlan.PROMISCUOUS
        ):
            raise NmstateValueError(
                "Disable promiscuous is only allowed on passthru mode"
            )
        if self.config_subtree.get(MacVlan.MODE) == MacVlan.Mode.UNKNOWN:
            raise NmstateValueError(
                "Mode unknown is not supported when appying the state"
            )

    def _validate_mandatory_properties(self):
        for prop in (MacVlan.MODE, MacVlan.BASE_IFACE):
            if prop not in self.config_subtree:
                raise NmstateValueError(
                    f"{self.type} tunnel {self.name} has missing mandatory"
                    f" property: {prop}"
                )
