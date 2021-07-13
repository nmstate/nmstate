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

import contextlib
import logging

from libnmstate.error import NmstateValueError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.validator import validate_list
from libnmstate.validator import validate_string

from ..state import state_match
from .base_iface import BaseIface


IANA_MULTICAST_MAC_ADDRESS_PREFIX = "01:00:5E"


class BondIface(BaseIface):
    _MODE_CHANGE_METADATA = "_bond_mode_changed"

    def sort_port(self):
        if self.port:
            self.raw[Bond.CONFIG_SUBTREE][Bond.PORT].sort()

    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._normalize_options_values()
        self._fix_bond_option_arp_monitor()

    @property
    def port(self):
        return self.raw.get(Bond.CONFIG_SUBTREE, {}).get(Bond.PORT, [])

    @property
    def is_controller(self):
        return True

    @property
    def is_virtual(self):
        return True

    @property
    def bond_mode(self):
        return self.raw.get(Bond.CONFIG_SUBTREE, {}).get(Bond.MODE)

    @property
    def bond_options(self):
        return self.raw.get(Bond.CONFIG_SUBTREE, {}).get(
            Bond.OPTIONS_SUBTREE, {}
        )

    @property
    def is_bond_mode_changed(self):
        return self.raw.get(BondIface._MODE_CHANGE_METADATA) is True

    def _set_bond_mode_changed_metadata(self, value):
        self.raw[BondIface._MODE_CHANGE_METADATA] = value

    def _generate_bond_mode_change_metadata(self, ifaces):
        if self.is_up:
            cur_iface = ifaces.get_cur_iface(self.name, self.type)
            if cur_iface and self.bond_mode != cur_iface.bond_mode:
                self._set_bond_mode_changed_metadata(True)

    def gen_metadata(self, ifaces):
        super().gen_metadata(ifaces)
        if not self.is_absent:
            self._generate_bond_mode_change_metadata(ifaces)

    def pre_edit_validation_and_cleanup(self):
        self._validate_bond_properties()
        super().pre_edit_validation_and_cleanup()
        if self.is_up and self.is_desired:
            self._discard_bond_option_when_mode_change()
            self._validate_bond_mode()
            self._fix_mac_restriced_mode()
            self._validate_miimon_conflict_with_arp_interval()
            self._validate_ad_actor_system_mac_address()

    def _validate_bond_properties(self):
        validate_string(
            self._info.get(Interface.COPY_MAC_FROM), Interface.COPY_MAC_FROM
        )
        validate_string(self.bond_mode, Bond.MODE)
        validate_list(self.port, Bond.PORT, elem_type=str)

    def _discard_bond_option_when_mode_change(self):
        if self.is_bond_mode_changed:
            logging.warning(
                "Discarding all current bond options as interface "
                f"{self.name} has bond mode changed"
            )
            self.raw[Bond.CONFIG_SUBTREE][
                Bond.OPTIONS_SUBTREE
            ] = self.original_desire_dict.get(Bond.CONFIG_SUBTREE, {}).get(
                Bond.OPTIONS_SUBTREE, {}
            )
            self._normalize_options_values()

    def _validate_bond_mode(self):
        if self.bond_mode is None:
            raise NmstateValueError(
                f"Bond interface {self.name} does not have bond mode defined"
            )

    def _fix_mac_restriced_mode(self):
        if self.is_in_mac_restricted_mode:
            if self.original_desire_dict.get(Interface.MAC):
                raise NmstateValueError(
                    "MAC address cannot be specified in bond interface along "
                    "with fail_over_mac active on active backup mode"
                )
            else:
                self.raw.pop(Interface.MAC, None)

    def _validate_miimon_conflict_with_arp_interval(self):
        bond_options = self.bond_options
        if bond_options.get("miimon") and bond_options.get("arp_interval"):
            raise NmstateValueError(
                "Bond option arp_interval is conflicting with miimon, "
                "please disable one of them by setting to 0"
            )

    @staticmethod
    def is_mac_restricted_mode(mode, bond_options):
        return (
            mode == BondMode.ACTIVE_BACKUP
            and bond_options.get("fail_over_mac") == "active"
        )

    @property
    def is_in_mac_restricted_mode(self):
        """
        Return True when Bond option does not allow MAC address defined.
        In MAC restricted mode means:
            Bond mode is BondMode.ACTIVE_BACKUP
            Bond option "fail_over_mac" is active.
        """
        return BondIface.is_mac_restricted_mode(
            self.bond_mode, self.bond_options
        )

    def _normalize_options_values(self):
        if self.bond_options:
            normalized_options = {}
            for option_name, option_value in self.bond_options.items():
                with contextlib.suppress(ValueError):
                    option_value = int(option_value)
                option_value = _get_bond_named_option_value_by_id(
                    option_name, option_value
                )
                normalized_options[option_name] = option_value
            self.bond_options.update(normalized_options)

    def _fix_bond_option_arp_monitor(self):
        """
        Adding 'arp_ip_target=""' when ARP monitor is disabled by
        `arp_interval=0`
        """
        if self.bond_options:
            _include_arp_ip_target_explictly_when_disable(
                self.raw[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
            )

    def state_for_verify(self):
        state = super().state_for_verify()
        if state.get(Bond.CONFIG_SUBTREE, {}).get(Bond.OPTIONS_SUBTREE):
            _include_arp_ip_target_explictly_when_disable(
                state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
            )
        return state

    def remove_port(self, port_name):
        self.raw[Bond.CONFIG_SUBTREE][Bond.PORT] = [
            s for s in self.port if s != port_name
        ]
        self.sort_port()

    def match_ignore_bond_options(self, current):
        self_state = self.state_for_verify()
        self_bond_options = self_state.get(Bond.CONFIG_SUBTREE, {}).pop(
            Bond.OPTIONS_SUBTREE, {}
        )
        current_state = current.state_for_verify()
        current_bond_options = current_state.get(Bond.CONFIG_SUBTREE, {}).pop(
            Bond.OPTIONS_SUBTREE, {}
        )
        for key, value in self_bond_options.items():
            (
                current_value,
                value_set,
            ) = self._normalize_bond_option_for_matching(
                current_bond_options.get(key), value
            )
            if current_value != value_set:
                if current_value is None:
                    logging.warning(
                        f"Desire iface {self.name} bond option "
                        f"{key}={value_set} is invalid in kernel for bond mode"
                        f" {self.bond_mode}"
                    )
                else:
                    logging.warning(
                        f"Desire iface {self.name} bond option "
                        f"{key}={value_set} does not match with kernel value:"
                        f" {current_value}"
                    )
        return state_match(self_state, current_state)

    def _normalize_bond_option_for_matching(self, current_value, value):
        """
        This is normalizing the values just for matching. This is required in
        order to avoid false warnings like:
            * Uppercase vs Lowercase
        """
        if isinstance(current_value, str) and isinstance(value, str):
            return current_value.lower(), value.lower()
        else:
            return current_value, value

    def _validate_ad_actor_system_mac_address(self):
        desire_mac = (
            self.original_desire_dict.get(Bond.CONFIG_SUBTREE, {})
            .get(Bond.OPTIONS_SUBTREE, {})
            .get("ad_actor_system")
        )
        if desire_mac and desire_mac.upper().startswith(
            IANA_MULTICAST_MAC_ADDRESS_PREFIX
        ):
            raise NmstateValueError(
                "The ad_actor_system bond option cannot be an IANA "
                "multicast address(prefix with "
                f"{IANA_MULTICAST_MAC_ADDRESS_PREFIX})"
            )


class _BondNamedOptions:
    AD_SELECT = "ad_select"
    ARP_ALL_TARGETS = "arp_all_targets"
    ARP_VALIDATE = "arp_validate"
    FAIL_OVER_MAC = "fail_over_mac"
    LACP_RATE = "lacp_rate"
    MODE = "mode"
    PRIMARY_RESELECT = "primary_reselect"
    XMIT_HASH_POLICY = "xmit_hash_policy"
    USE_CARRIER = "use_carrier"


_BOND_OPTIONS_NUMERIC_TO_NAMED_MAP = {
    _BondNamedOptions.AD_SELECT: ("stable", "bandwidth", "count"),
    _BondNamedOptions.ARP_ALL_TARGETS: ("any", "all"),
    _BondNamedOptions.ARP_VALIDATE: (
        "none",
        "active",
        "backup",
        "all",
        "filter",
        "filter_active",
        "filter_backup",
    ),
    _BondNamedOptions.FAIL_OVER_MAC: ("none", "active", "follow"),
    _BondNamedOptions.LACP_RATE: ("slow", "fast"),
    _BondNamedOptions.MODE: (
        "balance-rr",
        "active-backup",
        "balance-xor",
        "broadcast",
        "802.3ad",
        "balance-tlb",
        "balance-alb",
    ),
    _BondNamedOptions.PRIMARY_RESELECT: ("always", "better", "failure"),
    _BondNamedOptions.USE_CARRIER: (False, True),
    _BondNamedOptions.XMIT_HASH_POLICY: (
        "layer2",
        "layer3+4",
        "layer2+3",
        "encap2+3",
        "encap3+4",
        "vlan+srcmac",
    ),
}


def _get_bond_named_option_value_by_id(option_name, option_id_value):
    """
    Given an option name and its value, return a named option value
    if it exists.
    Return the same option value as inputted if:
    - The option name has no dual named and id values.
    - The option value is not numeric.
    - The option value has no corresponding named value (not in range).
    """
    option_value = _BOND_OPTIONS_NUMERIC_TO_NAMED_MAP.get(option_name)
    if option_value:
        with contextlib.suppress(ValueError, IndexError):
            return option_value[int(option_id_value)]
    return option_id_value


def _include_arp_ip_target_explictly_when_disable(bond_options):
    if (
        bond_options.get("arp_interval") == 0
        and "arp_ip_target" not in bond_options
    ):
        bond_options["arp_ip_target"] = ""
