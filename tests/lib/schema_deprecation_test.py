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

from libnmstate.schema import Bond
from libnmstate.schema import OVSBridge


def test_bond_deprecated_constants():
    with pytest.warns(FutureWarning) as record:
        deprecated_value = getattr(Bond, "SLAVES")

    assert len(record) == 1
    assert "SLAVES" in record[0].message.args[0]
    assert deprecated_value == "port"


def test_ovsbridge_slaves_subtree_deprecated_constants():
    with pytest.warns(FutureWarning) as record:
        deprecated_value = getattr(
            OVSBridge.Port.LinkAggregation, "SLAVES_SUBTREE"
        )

    assert len(record) == 1
    assert "SLAVES_SUBTREE" in record[0].message.args[0]
    assert deprecated_value == "port"


def test_ovsbridge_port_subtree_deprecated_constants():
    with pytest.warns(FutureWarning) as record:
        # pylint: disable=E1101
        deprecated_value = getattr(
            OVSBridge.Port.LinkAggregation.Slave, "NAME"
        )
        # pylint: enable=E1101

    assert len(record) == 1
    assert "Port" in record[0].message.args[0]
    assert deprecated_value == "name"
