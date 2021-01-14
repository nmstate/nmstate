#
# Copyright (c) 2020-2021 Red Hat, Inc.
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
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import VRF

from .testlib import assertlib
from .testlib import cmdlib


TEST_VRF0 = "test-vrf0"
TEST_VRF1 = "test-vrf1"
TEST_VRF_PORT0 = "eth1"
TEST_VRF_PORT1 = "eth2"
TEST_VRF_VETH0 = "veth0"
TEST_VRF_VETH1 = "veth1"
TEST_ROUTE_TABLE_ID0 = 100
TEST_ROUTE_TABLE_ID1 = 101
IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"


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


@pytest.fixture
def unmanaged_port_up():
    cmdlib.exec_cmd(
        f"ip link add {TEST_VRF_VETH0} type veth peer {TEST_VRF_VETH1}".split()
    )
    cmdlib.exec_cmd(f"ip link set {TEST_VRF_VETH0} up".split())
    cmdlib.exec_cmd(f"ip link set {TEST_VRF_VETH1} up".split())
    try:
        yield TEST_VRF_VETH0
    finally:
        cmdlib.exec_cmd(f"ip link del {TEST_VRF_VETH0}".split())


@pytest.fixture
def vrf1_with_unmanaged_port(unmanaged_port_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF1,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: [unmanaged_port_up],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID1,
        },
    }
    veth_iface_info = {
        Interface.NAME: unmanaged_port_up,
        Interface.TYPE: InterfaceType.ETHERNET,
        Interface.STATE: InterfaceState.UP,
    }
    libnmstate.apply({Interface.KEY: [vrf_iface_info, veth_iface_info]})
    try:
        yield vrf_iface_info
    finally:
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

    def test_port_holding_ip(self, vrf0_with_port0):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF_PORT0,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: False,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: False,
                        InterfaceIPv6.AUTOCONF: False,
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                    },
                }
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_takes_over_unmanaged_vrf(self, vrf1_with_unmanaged_port):
        pass
