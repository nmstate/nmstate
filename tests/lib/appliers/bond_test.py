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
import copy

import pytest

from libnmstate.appliers import bond
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.state import State


BOND1 = "bond1"


@pytest.mark.parametrize(
    ("option_name", "named_value", "id_value"),
    (
        ("ad_select", "stable", 0),
        ("ad_select", "bandwidth", 1),
        ("ad_select", "count", 2),
        ("arp_validate", "active", 1),
        ("arp_validate", "filter", 4),
        ("arp_validate", "filter_backup", 6),
        ("fail_over_mac", "none", 0),
        ("fail_over_mac", "active", 1),
        ("fail_over_mac", "follow", 2),
    ),
)
def test_numeric_to_named_option_value(option_name, id_value, named_value):
    assert named_value == bond.get_bond_named_option_value_by_id(
        option_name, id_value
    )


@pytest.mark.parametrize("option_value", ("a", 99))
def test_numeric_to_named_option_value_with_invalid_id(option_value):
    assert option_value == bond.get_bond_named_option_value_by_id(
        "ad_select", option_value
    )


def test_numeric_to_named_option_value_with_invalid_option_name():
    value = 0
    assert value == bond.get_bond_named_option_value_by_id("foo", value)


def test_discard_merged_data_on_mode_change_with_mode_changed():
    merged_iface_state = {
        bond.BOND_MODE_CHANGED_METADATA: True,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.OPTIONS_SUBTREE: {"lacp_rate": "fast", "miimon": "140"},
        },
    }
    desired_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.OPTIONS_SUBTREE: {"miimon": "140"},
        }
    }
    bond.discard_merged_data_on_mode_change(
        merged_iface_state, desired_iface_state
    )
    assert merged_iface_state == {
        bond.BOND_MODE_CHANGED_METADATA: True,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.OPTIONS_SUBTREE: {"miimon": "140"},
        },
    }


def test_discard_merged_data_on_mode_change_with_no_mode_changed():
    merged_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.LACP,
            Bond.OPTIONS_SUBTREE: {"lacp_rate": "fast", "miimon": "140"},
        },
    }
    desired_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.LACP,
            Bond.OPTIONS_SUBTREE: {"miimon": "140"},
        }
    }
    expected_iface_state = copy.deepcopy(merged_iface_state)
    bond.discard_merged_data_on_mode_change(
        merged_iface_state, desired_iface_state
    )
    assert merged_iface_state == expected_iface_state


def test_discard_merged_data_on_mode_change_with_option_not_defined():
    merged_iface_state = {
        bond.BOND_MODE_CHANGED_METADATA: True,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.LACP,
            Bond.OPTIONS_SUBTREE: {"lacp_rate": "fast", "miimon": "140"},
        },
    }
    desired_iface_state = {Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP}}
    bond.discard_merged_data_on_mode_change(
        merged_iface_state, desired_iface_state
    )
    assert merged_iface_state == {
        bond.BOND_MODE_CHANGED_METADATA: True,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.LACP,
            Bond.OPTIONS_SUBTREE: {},
        },
    }


def test_generate_bond_mode_change_metadata_with_mode_changed_and_full_state():
    current_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP},
                }
            ]
        }
    )
    desire_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN},
                }
            ]
        }
    )
    bond.generate_bond_mode_change_metadata(desire_state, current_state)

    assert desire_state.interfaces[BOND1][bond.BOND_MODE_CHANGED_METADATA]


def test_generate_bond_mode_change_metadata_with_mode_changed_and_no_type():
    current_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP},
                }
            ]
        }
    )
    desire_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN},
                }
            ]
        }
    )
    bond.generate_bond_mode_change_metadata(desire_state, current_state)

    assert desire_state.interfaces[BOND1][bond.BOND_MODE_CHANGED_METADATA]


def test_generate_bond_mode_change_metadata_without_mode_defined():
    current_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP},
                }
            ]
        }
    )
    desire_state = State({Interface.KEY: [{Interface.NAME: BOND1}]})
    bond.generate_bond_mode_change_metadata(desire_state, current_state)

    assert (
        bond.BOND_MODE_CHANGED_METADATA not in desire_state.interfaces[BOND1]
    )


def test_generate_bond_mode_change_metadata_with_new_bond():
    current_state = State({})
    desire_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP},
                }
            ]
        }
    )
    bond.generate_bond_mode_change_metadata(desire_state, current_state)

    assert (
        bond.BOND_MODE_CHANGED_METADATA not in desire_state.interfaces[BOND1]
    )


def test_generate_bond_mode_change_metadata_with_bond_removed():
    current_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.LACP},
                }
            ]
        }
    )
    desire_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND1,
                    Interface.STATE: InterfaceState.ABSENT,
                    Bond.CONFIG_SUBTREE: {Bond.MODE: BondMode.ROUND_ROBIN},
                }
            ]
        }
    )
    bond.generate_bond_mode_change_metadata(desire_state, current_state)

    assert (
        bond.BOND_MODE_CHANGED_METADATA not in desire_state.interfaces[BOND1]
    )


def test_generate_bond_mode_change_metadata_without_bond_interface():
    current_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "foo",
                    Interface.TYPE: InterfaceType.ETHERNET,
                }
            ]
        }
    )
    desire_state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "foo",
                    Interface.TYPE: InterfaceType.ETHERNET,
                }
            ]
        }
    )
    bond.generate_bond_mode_change_metadata(desire_state, current_state)

    assert (
        bond.BOND_MODE_CHANGED_METADATA not in desire_state.interfaces["foo"]
    )
