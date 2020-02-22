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

import pytest

from libnmstate.appliers import bond


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
