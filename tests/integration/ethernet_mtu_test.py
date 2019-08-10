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

from __future__ import absolute_import
import copy
import time

import pytest
import jsonschema as js

import libnmstate
from libnmstate import schema
from libnmstate.error import NmstateVerificationError

from .testlib import assertlib
from .testlib import statelib
from .testlib.env import TEST_NIC1
from .testlib.statelib import INTERFACES


@pytest.fixture(scope='function', autouse=True)
def test_nic1(test_nic1_up):
    pass


@pytest.fixture
def test_nic1_with_ipv6(test_nic1_up):
    ifstate = test_nic1_up[schema.Interface.KEY][0]
    ifstate[schema.Interface.IPV6][schema.InterfaceIPv6.ENABLED] = True
    libnmstate.apply(test_nic1_up)


def test_increase_iface_mtu():
    desired_state = statelib.show_only((TEST_NIC1,))
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 1900

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_iface_mtu():
    desired_state = statelib.show_only((TEST_NIC1,))
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 1400

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_upper_limit_jambo_iface_mtu():
    desired_state = statelib.show_only((TEST_NIC1,))
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 9000

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_increase_more_than_jambo_iface_mtu():
    desired_state = statelib.show_only((TEST_NIC1,))
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 10000

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_to_zero_iface_mtu():
    desired_state = statelib.show_only((TEST_NIC1,))
    origin_desired_state = copy.deepcopy(desired_state)
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 0

    with pytest.raises(NmstateVerificationError) as err:
        libnmstate.apply(desired_state)
    assert '-mtu: 0' in err.value.args[0]
    # FIXME: Drop the sleep when the waiting logic is implemented.
    time.sleep(2)
    assertlib.assert_state(origin_desired_state)


def test_decrease_to_negative_iface_mtu():
    desired_state = statelib.show_only((TEST_NIC1,))
    origin_desired_state = copy.deepcopy(desired_state)
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = -1

    with pytest.raises(js.ValidationError) as err:
        libnmstate.apply(desired_state)
    assert '-1' in err.value.args[0]
    assertlib.assert_state(origin_desired_state)


def test_decrease_to_ipv6_min_ethernet_frame_size_iface_mtu(
    test_nic1_with_ipv6
):
    desired_state = statelib.show_only((TEST_NIC1,))
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 1280

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_to_lower_than_min_ipv6_iface_mtu(test_nic1_with_ipv6):
    original_state = statelib.show_only((TEST_NIC1,))
    desired_state = copy.deepcopy(original_state)
    iface_state = desired_state[INTERFACES][0]
    iface_state['mtu'] = 1279

    with pytest.raises(NmstateVerificationError) as err:
        libnmstate.apply(desired_state)
    assert '1279' in err.value.args[0]
    # FIXME: Drop the sleep when the waiting logic is implemented.
    time.sleep(2)
    assertlib.assert_state(original_state)
