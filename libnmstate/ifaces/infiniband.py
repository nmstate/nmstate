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
from libnmstate.schema import InfiniBand
from libnmstate.schema import Interface
from libnmstate.validator import validate_string

from .base_iface import BaseIface


VALID_IB_MODES = [
    InfiniBand.Mode.DATAGRAM,
    InfiniBand.Mode.CONNECTED,
]


class InfiniBandIface(BaseIface):
    @property
    def parent(self):
        return self._ib_config.get(InfiniBand.BASE_IFACE)

    @property
    def _pkey(self):
        return self._ib_config.get(InfiniBand.PKEY)

    @property
    def need_parent(self):
        if not self._pkey or str(self._pkey) == str(InfiniBand.DEFAULT_PKEY):
            return False
        return True

    @property
    def _ib_config(self):
        return self.raw.get(InfiniBand.CONFIG_SUBTREE, {})

    def pre_edit_validation_and_cleanup(self):
        self._validate_infiniband_properties()
        if self.is_up:
            _cannonicalize_pkey(self.raw)
            self._validate_mandatory_properties()
            self._validate_interface_name_format_for_pkey_nic()
        super().pre_edit_validation_and_cleanup()

    def _validate_infiniband_properties(self):
        validate_string(
            self._ib_config.get(InfiniBand.MODE),
            InfiniBand.MODE,
            VALID_IB_MODES,
        )
        validate_string(self.parent, InfiniBand.BASE_IFACE)

    def _validate_mandatory_properties(self):
        if self.is_up:
            if InfiniBand.MODE not in self._ib_config:
                raise NmstateValueError(
                    f"InfiniBand interface {self.name} has missing "
                    f"mandatory property: {InfiniBand.MODE}"
                )

    def state_for_verify(self):
        state = super().state_for_verify()
        _cannonicalize_pkey(state)
        return state

    def _validate_interface_name_format_for_pkey_nic(self):
        if self.need_parent:
            pkey_str = f"{self._pkey:x}"
            expected_name = f"{self.parent}.{pkey_str}"
            if self.name != expected_name:
                raise NmstateValueError(
                    f"InfiniBand interface name {self.name} is invalid "
                    f"for specified pkey, should be {expected_name}"
                )


def _cannonicalize_pkey(iface_info):
    """
    * Set as 0xffff if pkey not defined
    * Convert pkey string to integer
    * Raise NmstateValueError when out of range(16 bites)
    """
    iface_name = iface_info[Interface.NAME]
    ib_config = iface_info.get(InfiniBand.CONFIG_SUBTREE, {})
    original_pkey = ib_config.get(InfiniBand.PKEY)
    is_invalid = False
    if original_pkey is None:
        ib_config[InfiniBand.PKEY] = 0xFFFF
    elif isinstance(original_pkey, str):
        if original_pkey.startswith("0x"):
            try:
                ib_config[InfiniBand.PKEY] = int(original_pkey, 16)
            except ValueError:
                is_invalid = True
        else:
            try:
                ib_config[InfiniBand.PKEY] = int(original_pkey, 10)
            except ValueError:
                is_invalid = True

    if (
        is_invalid
        or ib_config[InfiniBand.PKEY] > 0xFFFF
        or ib_config[InfiniBand.PKEY] <= 0
    ):
        raise NmstateValueError(
            f"Invalid infiniband pkey for interface {iface_name}: "
            f"{original_pkey}, should be integer or hex string in the range of"
            "1 - 0xffff"
        )
