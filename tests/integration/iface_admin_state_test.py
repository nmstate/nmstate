# SPDX-License-Identifier: Apache-2.0

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
