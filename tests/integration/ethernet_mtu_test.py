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
import copy
import time

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv6
from libnmstate.error import NmstateVerificationError

from .testlib import assertlib
from .testlib import statelib
from .testlib.iproutelib import ip_monitor_assert_stable_link_up
from .testlib.vlan import vlan_interface


@pytest.fixture(scope="function", autouse=True)
def eth1(eth1_up):
    pass


@pytest.fixture
def eth1_with_ipv6(eth1_up):
    ifstate = eth1_up[Interface.KEY][0]
    ifstate[Interface.IPV6][InterfaceIPv6.ENABLED] = True
    libnmstate.apply(eth1_up)


@pytest.mark.tier1
def test_increase_iface_mtu():
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 1900

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_decrease_iface_mtu():
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 1400

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_upper_limit_jambo_iface_mtu():
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 9000

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_increase_more_than_jambo_iface_mtu():
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 10000

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_to_ipv6_min_ethernet_frame_size_iface_mtu(eth1_with_ipv6):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 1280

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_decrease_to_lower_than_min_ipv6_iface_mtu(eth1_with_ipv6):
    original_state = statelib.show_only(("eth1",))
    desired_state = copy.deepcopy(original_state)
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 1279

    with pytest.raises(NmstateVerificationError) as err:
        libnmstate.apply(desired_state)
    assert "1279" in err.value.args[0]
    # FIXME: Drop the sleep when the waiting logic is implemented.
    time.sleep(2)
    assertlib.assert_state(original_state)


def test_mtu_without_ipv6(eth1_up):
    eth1_up[Interface.KEY][0][Interface.MTU] = 576
    libnmstate.apply(eth1_up)
    assertlib.assert_state(eth1_up)


@pytest.mark.tier1
def test_set_mtu_on_two_vlans_with_a_shared_base(eth1_up):
    base_ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    v101 = vlan_interface("eth1.101", 101, base_ifname)
    v102 = vlan_interface("eth1.102", 102, base_ifname)
    with v101 as v101_state, v102 as v102_state:
        desired_state = {
            Interface.KEY: [
                eth1_up[Interface.KEY][0],
                v101_state[Interface.KEY][0],
                v102_state[Interface.KEY][0],
            ]
        }
        for iface_state in desired_state[Interface.KEY]:
            iface_state[Interface.MTU] = 2000

        libnmstate.apply(desired_state)

        assertlib.assert_state(desired_state)


@pytest.mark.tier1
@ip_monitor_assert_stable_link_up("eth1")
def test_change_mtu_with_stable_link_up(eth1_up):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 1900

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.fixture(scope="function")
def eth1_up_with_mtu_1900(eth1_up):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.MTU] = 1900

    libnmstate.apply(desired_state)
    yield desired_state


def test_empty_state_preserve_the_old_mtu(eth1_up_with_mtu_1900):
    desired_state = eth1_up_with_mtu_1900
    libnmstate.apply({Interface.KEY: [{Interface.NAME: "eth1"}]})

    assertlib.assert_state(desired_state)
