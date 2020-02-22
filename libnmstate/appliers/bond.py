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

import contextlib

from libnmstate.schema import Bond
from libnmstate.schema import BondMode


class BondNamedOptions:
    AD_SELECT = "ad_select"
    ARP_ALL_TARGETS = "arp_all_targets"
    ARP_VALIDATE = "arp_validate"
    FAIL_OVER_MAC = "fail_over_mac"
    LACP_RATE = "lacp_rate"
    MODE = "mode"
    PRIMARY_RESELECT = "primary_reselect"
    XMIT_HASH_POLICY = "xmit_hash_policy"


BOND_OPTIONS_NUMERIC_TO_NAMED_MAP = {
    BondNamedOptions.AD_SELECT: ("stable", "bandwidth", "count"),
    BondNamedOptions.ARP_ALL_TARGETS: ("any", "all"),
    BondNamedOptions.ARP_VALIDATE: (
        "none",
        "active",
        "backup",
        "all",
        "filter",
        "filter_active",
        "filter_backup",
    ),
    BondNamedOptions.FAIL_OVER_MAC: ("none", "active", "follow"),
    BondNamedOptions.LACP_RATE: ("slow", "fast"),
    BondNamedOptions.MODE: (
        "balance-rr",
        "active-backup",
        "balance-xor",
        "broadcast",
        "802.3ad",
        "balance-tlb",
        "balance-alb",
    ),
    BondNamedOptions.PRIMARY_RESELECT: ("always", "better", "failure"),
    BondNamedOptions.XMIT_HASH_POLICY: (
        "layer2",
        "layer3+4",
        "layer2+3",
        "encap2+3",
        "encap3+4",
    ),
}


def get_bond_slaves_from_state(iface_state, default=()):
    return iface_state.get(Bond.CONFIG_SUBTREE, {}).get(Bond.SLAVES, default)


def is_in_mac_restricted_mode(bond_options):
    """
    Return True when Bond option does not allow MAC address defined.
    In MAC restricted mode means:
        Bond mode is BondMode.ACTIVE_BACKUP
        Bond option "fail_over_mac" is active.
    """
    return BondMode.ACTIVE_BACKUP == bond_options.get(
        Bond.MODE
    ) and bond_options.get("fail_over_mac") in ("1", 1, "active",)


def normalize_options_values(iface_state):
    bond_state = iface_state.get(Bond.CONFIG_SUBTREE, {})
    options = bond_state.get(Bond.OPTIONS_SUBTREE)
    if options:
        normalized_options = {}
        for option_name, option_value in options.items():
            with contextlib.suppress(ValueError):
                option_value = int(option_value)
            option_value = get_bond_named_option_value_by_id(
                option_name, option_value
            )
            normalized_options[option_name] = option_value
        options.update(normalized_options)


def get_bond_named_option_value_by_id(option_name, option_id_value):
    """
    Given an option name and its value, return a named option value
    if it exists.
    Return the same option value as inputted if:
    - The option name has no dual named and id values.
    - The option value is not numeric.
    - The option value has no corresponding named value (not in range).
    """
    option_value = BOND_OPTIONS_NUMERIC_TO_NAMED_MAP.get(option_name)
    if option_value:
        with contextlib.suppress(ValueError, IndexError):
            return option_value[int(option_id_value)]
    return option_id_value
