# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

import os

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import InfiniBand
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge

from .testlib import assertlib
from .testlib import statelib
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import linux_bridge
from .testlib.bridgelib import add_port_to_bridge


TEST_BRIDGE0 = "linux-br0"
TEST_BOND99 = "bond99"
TEST_PKEY1 = "0x80fe"
TEST_PKEY2 = "0x80ff"

IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"

TEST_STATIC_IPV4_CONFIG = {
    InterfaceIPv4.ENABLED: True,
    InterfaceIPv4.DHCP: False,
    InterfaceIPv4.ADDRESS: [
        {
            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
        }
    ],
}

TEST_STATIC_IPV6_CONFIG = {
    InterfaceIPv6.ENABLED: True,
    InterfaceIPv6.DHCP: False,
    InterfaceIPv6.AUTOCONF: False,
    InterfaceIPv6.ADDRESS: [
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        }
    ],
}


def _test_nic_name():
    return os.environ.get("TEST_REAL_NIC")


def _test_ib_mode():
    return (
        InfiniBand.Mode.CONNECTED
        if os.environ.get("TEST_IB_CONNECTED_MODE")
        else InfiniBand.Mode.DATAGRAM
    )


def _gen_ib_iface_info(
    base_iface,
    pkey=InfiniBand.DEFAULT_PKEY,
    mode=InfiniBand.Mode.DATAGRAM,
):
    if pkey == InfiniBand.DEFAULT_PKEY:
        iface_name = base_iface
        base_iface = ""
    else:
        iface_name = f"{base_iface}.{pkey[2:]}"

    return {
        Interface.NAME: iface_name,
        Interface.TYPE: InterfaceType.INFINIBAND,
        InfiniBand.CONFIG_SUBTREE: {
            InfiniBand.PKEY: pkey,
            InfiniBand.MODE: mode,
            InfiniBand.BASE_IFACE: base_iface,
        },
    }


@pytest.fixture
def ib_base_nic():
    iface_info = _gen_ib_iface_info(_test_nic_name(), mode=_test_ib_mode())
    libnmstate.apply({Interface.KEY: [iface_info]})
    yield iface_info
    iface_info[Interface.STATE] = InterfaceState.ABSENT
    libnmstate.apply(
        {Interface.KEY: [iface_info]},
        verify_change=False,
    )


@pytest.fixture
def ib_pkey_nic1(ib_base_nic):
    iface_info = _gen_ib_iface_info(
        _test_nic_name(), TEST_PKEY1, _test_ib_mode()
    )
    libnmstate.apply({Interface.KEY: [iface_info]})
    yield iface_info
    iface_info[Interface.STATE] = InterfaceState.ABSENT
    libnmstate.apply(
        {Interface.KEY: [iface_info]},
        verify_change=False,
    )


@pytest.fixture
def ib_pkey_nic2(ib_base_nic):
    iface_info = _gen_ib_iface_info(
        _test_nic_name(), TEST_PKEY2, _test_ib_mode()
    )
    libnmstate.apply({Interface.KEY: [iface_info]})
    yield iface_info
    iface_info[Interface.STATE] = InterfaceState.ABSENT
    libnmstate.apply(
        {Interface.KEY: [iface_info]},
        verify_change=False,
    )


@pytest.fixture
def empty_test_bridge():
    bridge_config = {}
    with linux_bridge(TEST_BRIDGE0, bridge_config) as state:
        yield state


@pytest.fixture
def empty_test_bond():
    with bond_interface(TEST_BOND99, []) as state:
        yield state


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC(TEST_IB_CONNECTED_MODE optionally) "
    "for infiniband test",
)
class TestInfiniBand:
    def test_create_and_remove_pkey_nic(self, ib_base_nic):
        desired_state = {
            Interface.KEY: [
                _gen_ib_iface_info(
                    _test_nic_name(), TEST_PKEY1, _test_ib_mode()
                )
            ]
        }
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
        finally:
            desired_state[Interface.KEY][0][
                Interface.STATE
            ] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

    def test_change_mtu_of_base_nic(self, ib_base_nic):
        desired_state = {
            Interface.KEY: [
                {Interface.NAME: _test_nic_name(), Interface.MTU: 1280}
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_change_mtu_of_pkey_nic(self, ib_pkey_nic1):
        iface_info = ib_pkey_nic1
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: iface_info[Interface.NAME],
                        Interface.MTU: 1280,
                    }
                ]
            }
        )

        iface_info[Interface.MTU] = 1280
        desired_state = {Interface.KEY: [iface_info]}
        assertlib.assert_state_match(desired_state)

    def test_remove_base_nic_got_pkey_nics_removed_automatically(
        self, ib_pkey_nic1
    ):
        pkey_iface_name = ib_pkey_nic1[Interface.NAME]
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: _test_nic_name(),
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )
        current_state = statelib.show_only((pkey_iface_name,))
        if len(current_state[Interface.KEY]):
            # The interface might be deleted after base interface
            cur_pkey_iface_info = current_state[Interface.KEY][0]
            assert cur_pkey_iface_info[Interface.STATE] == InterfaceState.DOWN

    def test_change_ip_of_base_nic(self, ib_base_nic):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: _test_nic_name(),
                    Interface.IPV4: TEST_STATIC_IPV4_CONFIG,
                    Interface.IPV6: TEST_STATIC_IPV6_CONFIG,
                }
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_change_ip_of_pkey_nic(self, ib_pkey_nic1):
        iface_name = ib_pkey_nic1[Interface.NAME]
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: iface_name,
                    Interface.IPV4: TEST_STATIC_IPV4_CONFIG,
                    Interface.IPV6: TEST_STATIC_IPV6_CONFIG,
                }
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_add_base_nic_to_linux_bridge(
        self, empty_test_bridge, ib_base_nic
    ):
        """
        The InfiniBand is IP over IB, hence there is ethernet layer for
        IPoIB NIC, so there is no way for adding a IPoIB NIC to bridge
        """
        bridge_iface_info = empty_test_bridge[Interface.KEY][0]
        bridge_iface_info[LinuxBridge.CONFIG_SUBTREE] = {}
        add_port_to_bridge(
            bridge_iface_info[LinuxBridge.CONFIG_SUBTREE], _test_nic_name()
        )
        desired_state = {Interface.KEY: [bridge_iface_info]}

        with pytest.raises(NmstateValueError):
            libnmstate.apply(desired_state)

    def test_add_pkey_nic_to_linux_bridge(
        self, empty_test_bridge, ib_pkey_nic1
    ):
        pkey_iface_name = ib_pkey_nic1[Interface.NAME]
        bridge_iface_info = empty_test_bridge[Interface.KEY][0]
        bridge_iface_info[LinuxBridge.CONFIG_SUBTREE] = {}
        add_port_to_bridge(
            bridge_iface_info[LinuxBridge.CONFIG_SUBTREE], pkey_iface_name
        )
        desired_state = {Interface.KEY: [bridge_iface_info]}

        with pytest.raises(NmstateValueError):
            libnmstate.apply(desired_state)

    def test_add_base_nic_to_active_backup_bond(
        self, empty_test_bond, ib_base_nic
    ):
        with bond_interface(
            TEST_BOND99, [_test_nic_name()], create=False
        ) as desired_state:
            desired_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.MODE
            ] = BondMode.ACTIVE_BACKUP
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)

    def test_add_pkey_nic_to_active_backup_bond(
        self,
        empty_test_bond,
        ib_pkey_nic1,
        ib_pkey_nic2,
    ):
        port1_name = ib_pkey_nic1[Interface.NAME]
        port2_name = ib_pkey_nic2[Interface.NAME]
        with bond_interface(
            TEST_BOND99, [port1_name, port2_name], create=False
        ) as desired_state:
            desired_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.MODE
            ] = BondMode.ACTIVE_BACKUP
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)

    def test_expect_exception_when_adding_base_nic_to_round_robin_bond(
        self, empty_test_bond, ib_base_nic
    ):
        """
        IP over InfiniBand interface is only allowd to be port of active-backup
        bond.
        """
        with bond_interface(
            TEST_BOND99, [_test_nic_name()], create=False
        ) as desired_state:
            desired_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.MODE
            ] = BondMode.ROUND_ROBIN
            with pytest.raises(NmstateValueError):
                libnmstate.apply(desired_state)

    def test_expect_exception_when_adding_pkey_nic_to_round_robin_bond(
        self,
        empty_test_bond,
        ib_pkey_nic1,
        ib_pkey_nic2,
    ):
        """
        IP over InfiniBand interface is only allowd to be port of active-backup
        bond.
        """
        port1_name = ib_pkey_nic1[Interface.NAME]
        port2_name = ib_pkey_nic2[Interface.NAME]
        with bond_interface(
            TEST_BOND99, [port1_name, port2_name], create=False
        ) as desired_state:
            desired_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.MODE
            ] = BondMode.ROUND_ROBIN
            with pytest.raises(NmstateValueError):
                libnmstate.apply(desired_state)
