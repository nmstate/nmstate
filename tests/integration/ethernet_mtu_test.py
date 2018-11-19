#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import absolute_import
import copy
import time

import pytest
import jsonschema as js

from libnmstate import netapplier

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES


@pytest.fixture(scope='function', autouse=True)
def eth1(eth1_up):
    pass


def test_increase_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 1900

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 1400

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_upper_limit_jambo_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 9000

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_increase_more_than_jambo_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 10000

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_to_zero_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    origin_desired_state = copy.deepcopy(desired_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 0

    with pytest.raises(netapplier.DesiredStateIsNotCurrentError) as err:
        netapplier.apply(desired_state)
    assert '-mtu: 0' in err.value.args[0]
    # FIXME: Drop the sleep when the waiting logic is implemented.
    time.sleep(2)
    assertlib.assert_state(origin_desired_state)


def test_decrease_to_negative_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    origin_desired_state = copy.deepcopy(desired_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = -1

    with pytest.raises(js.ValidationError) as err:
        netapplier.apply(desired_state)
    assert '-1' in err.value.args[0]
    assertlib.assert_state(origin_desired_state)


def test_decrease_to_ipv6_min_ethernet_frame_size_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 1280

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_to_lower_than_min_ipv6_iface_mtu():
    original_state = statelib.show_only(('eth1',))
    desired_state = copy.deepcopy(original_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['mtu'] = 1279

    with pytest.raises(netapplier.DesiredStateIsNotCurrentError) as err:
        netapplier.apply(desired_state)
    assert '1279' in err.value.args[0]
    # FIXME: Drop the sleep when the waiting logic is implemented.
    time.sleep(2)
    assertlib.assert_state(original_state)
