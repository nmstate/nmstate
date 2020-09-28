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

import libnmstate

from libnmstate.error import NmstateNotSupportedError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import VRF

from .testlib import assertlib

TEST_VRF0 = "test-vrf0"
TEST_VRF1 = "test-vrf1"
TEST_VRF_PORT0 = "eth1"
TEST_VRF_PORT1 = "eth2"
TEST_ROUTE_TABLE_ID0 = 100
TEST_ROUTE_TABLE_ID1 = 101


@pytest.fixture
def vrf0_with_port0(port1_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF0,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: [TEST_VRF_PORT0],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID0,
        },
    }
    libnmstate.apply({Interface.KEY: [vrf_iface_info]})
    yield vrf_iface_info
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    assertlib.assert_absent(TEST_VRF0)


@pytest.fixture
def vrf1_with_port1(port1_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF1,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: [TEST_VRF_PORT1],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID1,
        },
    }
    libnmstate.apply({Interface.KEY: [vrf_iface_info]})
    yield vrf_iface_info
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    assertlib.assert_absent(TEST_VRF1)


class TestVrf:
    def test_create_and_remove(self, vrf0_with_port0):
        pass

    def test_change_route_table_id(self, vrf0_with_port0):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.ROUTE_TABLE_ID] += 1
        desired_state = {Interface.KEY: [iface_info]}
        with pytest.raises(NmstateNotSupportedError):
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)

    def test_create_with_empty_ports(self):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF0,
                    Interface.TYPE: InterfaceType.VRF,
                    VRF.CONFIG_SUBTREE: {
                        VRF.PORT_SUBTREE: [],
                        VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID0,
                    },
                }
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_add_and_remove_port(self, vrf0_with_port0, port1_up):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].append(TEST_VRF_PORT1)
        desired_state = {Interface.KEY: [iface_info]}
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].remove(TEST_VRF_PORT1)
        desired_state = {Interface.KEY: [iface_info]}
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_remove_port(self, vrf0_with_port0):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = []
        desired_state = {Interface.KEY: [iface_info]}
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_remove_all_ports(self, vrf0_with_port0):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = []
        desired_state = {Interface.KEY: [iface_info]}
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_moving_port_from_other_vrf(
        self, vrf0_with_port0, vrf1_with_port1
    ):
        vrf0_iface = vrf0_with_port0
        vrf1_iface = vrf1_with_port1
        vrf0_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = []
        vrf1_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [
            TEST_VRF_PORT0,
            TEST_VRF_PORT1,
        ]

        desired_state = {Interface.KEY: [vrf0_iface, vrf1_iface]}
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_swaping_port(self, vrf0_with_port0, vrf1_with_port1):
        vrf0_iface = vrf0_with_port0
        vrf1_iface = vrf1_with_port1
        vrf0_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [TEST_VRF_PORT1]
        vrf1_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [TEST_VRF_PORT0]
        desired_state = {Interface.KEY: [vrf0_iface, vrf1_iface]}
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
