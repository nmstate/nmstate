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

import pytest
import jsonschema as js

from libnmstate import netapplier

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES

# FIXME: Once IPv6 disabling is supported, below IPv6 codes should be removed.


def test_increase_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['mtu'] = 1900
    eth1_desired_state['ipv6']['enabled'] = True

    netapplier.apply(copy.deepcopy(desired_state))

    assertlib.assert_state(desired_state)


def test_decrease_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['mtu'] = 1000

    netapplier.apply(copy.deepcopy(desired_state))

    assertlib.assert_state(desired_state)


def test_upper_limit_jambo_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['mtu'] = 9000
    eth1_desired_state['ipv6']['enabled'] = True

    netapplier.apply(copy.deepcopy(desired_state))

    assertlib.assert_state(desired_state)


def test_increase_more_than_jambo_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['mtu'] = 10000
    eth1_desired_state['ipv6']['enabled'] = True

    netapplier.apply(copy.deepcopy(desired_state))

    assertlib.assert_state(desired_state)


def test_decrease_to_zero_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    origin_desired_state = copy.deepcopy(desired_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['mtu'] = 0
    eth1_desired_state['ipv6']['enabled'] = True

    with pytest.raises(netapplier.DesiredStateIsNotCurrentError) as err:
        netapplier.apply(copy.deepcopy(desired_state))
    assert '-mtu: 0' in err.value.args[0]
    assertlib.assert_state(origin_desired_state)


def test_decrease_to_negative_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    origin_desired_state = copy.deepcopy(desired_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['mtu'] = -1
    eth1_desired_state['ipv6']['enabled'] = True

    with pytest.raises(js.ValidationError) as err:
        netapplier.apply(copy.deepcopy(desired_state))
    assert '-1' in err.value.args[0]
    assertlib.assert_state(origin_desired_state)


def test_decrease_to_min_ethernet_frame_size_iface_mtu():
    desired_state = statelib.show_only(('eth1',))
    origin_desired_state = copy.deepcopy(desired_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    # the min is 64 - 18 = 46
    eth1_desired_state['mtu'] = 40
    eth1_desired_state['ipv6']['enabled'] = True

    with pytest.raises(netapplier.DesiredStateIsNotCurrentError) as err:
        netapplier.apply(copy.deepcopy(desired_state))
    assert '-mtu: 40' in err.value.args[0]
    assertlib.assert_state(origin_desired_state)
