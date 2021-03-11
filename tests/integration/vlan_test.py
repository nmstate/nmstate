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

from contextlib import contextmanager
import time

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateLibnmError
from libnmstate.schema import VLAN
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from .testlib import assertlib
from .testlib import statelib
from .testlib.assertlib import assert_mac_address
from .testlib.vlan import vlan_interface

VLAN_IFNAME = "eth1.101"
VLAN2_IFNAME = "eth1.102"


@pytest.mark.tier1
def test_add_and_remove_vlan(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ) as desired_state:
        assertlib.assert_state(desired_state)

    current_state = statelib.show_only((VLAN_IFNAME,))
    assert not current_state[Interface.KEY]


@pytest.fixture
def vlan_on_eth1(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ) as desired_state:
        base_iface_name = desired_state[Interface.KEY][0][VLAN.CONFIG_SUBTREE][
            VLAN.BASE_IFACE
        ]
        iface_states = statelib.show_only((base_iface_name, VLAN_IFNAME))
        yield iface_states


@pytest.mark.tier1
def test_vlan_iface_uses_the_mac_of_base_iface(vlan_on_eth1):
    assert_mac_address(vlan_on_eth1)


def test_add_and_remove_two_vlans_on_same_iface(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        assertlib.assert_state(desired_state)

    vlan_interfaces = [i[Interface.NAME] for i in desired_state[Interface.KEY]]
    current_state = statelib.show_only(vlan_interfaces)
    assert not current_state[Interface.KEY]


@pytest.mark.tier1
def test_two_vlans_on_eth1_change_mtu(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        eth1_state = eth1_up[Interface.KEY][0]
        desired_state[Interface.KEY].append(eth1_state)
        for iface in desired_state[Interface.KEY]:
            iface[Interface.MTU] = 2000
        libnmstate.apply(desired_state)

        eth1_102_state = next(
            ifstate
            for ifstate in desired_state[Interface.KEY]
            if ifstate[Interface.NAME] == VLAN2_IFNAME
        )
        eth1_state[Interface.MTU] = 2200
        eth1_102_state[Interface.MTU] = 2200
        libnmstate.apply(desired_state)

        eth1_vlan_iface_cstate = statelib.show_only((VLAN_IFNAME,))
        assert eth1_vlan_iface_cstate[Interface.KEY][0][Interface.MTU] == 2000


@pytest.mark.tier1
def test_two_vlans_on_eth1_change_base_iface_mtu(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        eth1_state = eth1_up[Interface.KEY][0]
        desired_state[Interface.KEY].append(eth1_state)
        for iface in desired_state[Interface.KEY]:
            iface[Interface.MTU] = 2000
        libnmstate.apply(desired_state)

        eth1_state[Interface.MTU] = 2200
        libnmstate.apply(eth1_up)
        eth1_vlan_iface_cstate = statelib.show_only((VLAN_IFNAME,))
        assert eth1_vlan_iface_cstate[Interface.KEY][0][Interface.MTU] == 2000


@pytest.mark.tier1
def test_two_vlans_on_eth1_change_mtu_rollback(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        eth1_state = eth1_up[Interface.KEY][0]
        desired_state[Interface.KEY].append(eth1_state)
        for iface in desired_state[Interface.KEY]:
            iface[Interface.MTU] = 2000
        libnmstate.apply(desired_state)

        for iface in desired_state[Interface.KEY]:
            iface[Interface.MTU] = 2200
        libnmstate.apply(desired_state, commit=False)
        libnmstate.rollback()

        time.sleep(5)  # Give some time for NetworkManager to rollback

        eth1_vlan_iface_cstate = statelib.show_only((VLAN_IFNAME,))
        assert eth1_vlan_iface_cstate[Interface.KEY][0][Interface.MTU] == 2000


def test_rollback_for_vlans(eth1_up):
    current_state = libnmstate.show()
    desired_state = create_two_vlans_state()

    desired_state[Interface.KEY][1]["invalid_key"] = "foo"
    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(desired_state)

    time.sleep(5)  # Give some time for NetworkManager to rollback
    current_state_after_apply = libnmstate.show()
    assert current_state == current_state_after_apply


def test_set_vlan_iface_down(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: VLAN_IFNAME,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )

        assertlib.assert_absent(VLAN_IFNAME)


def test_add_new_base_iface_with_vlan():
    iface_base = "dummy00"
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "dummy00.101",
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {
                    VLAN.ID: 101,
                    VLAN.BASE_IFACE: iface_base,
                },
            },
            {
                Interface.NAME: iface_base,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
            },
        ]
    }
    try:
        libnmstate.apply(desired_state)
    finally:
        for ifstate in desired_state[Interface.KEY]:
            ifstate[Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(desired_state, verify_change=False)


@contextmanager
def two_vlans_on_eth1():
    desired_state = create_two_vlans_state()
    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: VLAN_IFNAME,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                    {
                        Interface.NAME: VLAN2_IFNAME,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                ]
            }
        )


def create_two_vlans_state():
    return {
        Interface.KEY: [
            {
                Interface.NAME: VLAN_IFNAME,
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: "eth1"},
            },
            {
                Interface.NAME: VLAN2_IFNAME,
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 102, VLAN.BASE_IFACE: "eth1"},
            },
        ]
    }


@pytest.mark.xfail(
    reason="https://bugzilla.redhat.com/1722352",
    strict=True,
    raises=NmstateLibnmError,
)
def test_change_vlan_id(eth1_up):
    vlana_name = "vlan.a"
    vlanb_name = "vlan.b"
    with vlan_interface(
        vlana_name, 201, eth1_up[Interface.KEY][0][Interface.NAME]
    ), vlan_interface(
        vlanb_name, 202, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        # modify full options to check if all of they will be preserved
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: vlana_name,
                    Interface.MTU: 1280,
                    Interface.MAC: "d4:ee:07:25:42:5a",
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: "2001:db8:1::1",
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                    },
                },
                {
                    Interface.NAME: vlanb_name,
                    Interface.MTU: 1280,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                        InterfaceIPv4.AUTO_DNS: False,
                        InterfaceIPv4.AUTO_GATEWAY: False,
                        InterfaceIPv4.AUTO_ROUTES: False,
                        InterfaceIPv4.AUTO_ROUTE_TABLE_ID: 100,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.AUTO_DNS: True,
                        InterfaceIPv6.AUTO_GATEWAY: True,
                        InterfaceIPv6.AUTO_ROUTES: True,
                        InterfaceIPv6.AUTO_ROUTE_TABLE_ID: 100,
                    },
                },
            ]
        }

        libnmstate.apply(desired_state)
        base_state = {}
        base_state[Interface.KEY] = libnmstate.show().pop(Interface.KEY)
        for iface in base_state[Interface.KEY]:
            if iface[Interface.NAME] == vlana_name:
                iface[VLAN.CONFIG_SUBTREE][VLAN.ID] = 1001
            elif iface[Interface.NAME] == vlanb_name:
                iface[VLAN.CONFIG_SUBTREE][VLAN.ID] = 1002

        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: vlana_name,
                    VLAN.CONFIG_SUBTREE: {VLAN.ID: 1001},
                },
                {
                    Interface.NAME: vlanb_name,
                    VLAN.CONFIG_SUBTREE: {VLAN.ID: 1002},
                },
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(base_state)
