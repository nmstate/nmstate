# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

import libnmstate

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from .testlib import assertlib


def test_set_a_down_iface_down(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.DOWN,
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.xfail(
    raises=AssertionError,
    reason="Some ifaces cannot be removed",
    strict=True,
)
def test_removing_a_non_removable_iface(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.ABSENT,
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_set_iface_down_without_type(eth1_up):
    desired_state = {
        Interface.KEY: [
            {Interface.NAME: "eth1", Interface.STATE: InterfaceState.DOWN}
        ]
    }
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_change_iface_without_type(eth1_up):
    desired_state = {
        Interface.KEY: [{Interface.NAME: "eth1", Interface.MTU: 1400}]
    }
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
