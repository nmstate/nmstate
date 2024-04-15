# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Bridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Veth
from libnmstate.schema import VLAN

from .testlib import assertlib
from .testlib import statelib
from .testlib.veth import veth_interface


VETH1 = "veth1"
VETH1PEER = "veth1peer"
VETH2PEER = "veth2peer"
VETH1_VLAN = "veth1.0"


class TestVeth:
    def test_eth_with_veth_conf(self, eth1_up):
        d_state = {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Veth.CONFIG_SUBTREE: {
                        Veth.PEER: VETH1PEER,
                    },
                },
                {
                    Interface.NAME: VETH1PEER,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                },
            ]
        }
        with pytest.raises(NmstateValueError):
            libnmstate.apply(d_state)

    @pytest.mark.tier1
    def test_add_veth_with_ethernet_peer(self):
        d_state = {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.TYPE: Veth.TYPE,
                    Interface.STATE: InterfaceState.UP,
                    Veth.CONFIG_SUBTREE: {
                        Veth.PEER: VETH1PEER,
                    },
                },
                {
                    Interface.NAME: VETH1PEER,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                },
            ]
        }
        try:
            libnmstate.apply(d_state)
            assertlib.assert_state_match(d_state)
        finally:
            d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
            d_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply(d_state)

    @pytest.mark.tier1
    def test_add_with_peer_not_mentioned_in_desire(self):
        with veth_interface(VETH1, VETH1PEER) as desired_state:
            assertlib.assert_state(desired_state)

        assertlib.assert_absent(VETH1)
        assertlib.assert_absent(VETH1PEER)

    @pytest.mark.tier1
    def test_add_and_remove_veth_kernel_mode(self):
        with veth_interface(
            VETH1, VETH1PEER, kernel_mode=True
        ) as desired_state:
            assertlib.assert_state(desired_state)

        assertlib.assert_absent(VETH1)
        assertlib.assert_absent(VETH1PEER)

    @pytest.mark.tier1
    def test_add_veth_with_veth_peer_in_desire(self):
        with veth_interface_both_up(VETH1, VETH1PEER):
            c_state = statelib.show_only(
                (
                    VETH1,
                    VETH1PEER,
                )
            )
            assert (
                c_state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
            )
            assert (
                c_state[Interface.KEY][1][Interface.STATE] == InterfaceState.UP
            )

        assertlib.assert_absent(VETH1)
        assertlib.assert_absent(VETH1PEER)

    @pytest.mark.tier1
    def test_add_veth_as_bridge_port(self):
        with veth_interface(VETH1, VETH1PEER):
            with bridges_with_port() as desired_state:
                assertlib.assert_state_match(desired_state)

    @pytest.mark.tier1
    def test_modify_veth_peer(self):
        with veth_interface(VETH1, VETH1PEER) as d_state:
            d_state[Interface.KEY][0][Veth.CONFIG_SUBTREE][
                Veth.PEER
            ] = VETH2PEER
            libnmstate.apply(d_state)

            c_state = statelib.show_only(
                (
                    VETH1,
                    VETH2PEER,
                )
            )
            assert (
                c_state[Interface.KEY][0][Veth.CONFIG_SUBTREE][Veth.PEER]
                == VETH2PEER
            )
            assert c_state[Interface.KEY][1][Interface.NAME] == VETH2PEER

    @pytest.mark.tier1
    def test_veth_as_vlan_base_iface(self):
        d_state = {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.TYPE: InterfaceType.VETH,
                    Interface.STATE: InterfaceState.UP,
                    Veth.CONFIG_SUBTREE: {
                        Veth.PEER: VETH1PEER,
                    },
                },
                {
                    Interface.NAME: VETH1_VLAN,
                    Interface.TYPE: InterfaceType.VLAN,
                    Interface.STATE: InterfaceState.UP,
                    VLAN.CONFIG_SUBTREE: {
                        VLAN.BASE_IFACE: VETH1,
                        VLAN.ID: 0,
                    },
                },
            ]
        }
        libnmstate.apply(d_state)

        c_state = statelib.show_only(
            (
                VETH1,
                VETH1_VLAN,
            )
        )
        assert c_state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
        assert c_state[Interface.KEY][1][Interface.STATE] == InterfaceState.UP

        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)

    @pytest.mark.tier1
    def test_veth_enable_and_disable_accept_all_mac_addresses(self):
        with veth_interface(VETH1, VETH1PEER) as d_state:
            d_state[Interface.KEY][0][
                Interface.ACCEPT_ALL_MAC_ADDRESSES
            ] = True
            libnmstate.apply(d_state)
            assertlib.assert_state(d_state)

            d_state[Interface.KEY][0][
                Interface.ACCEPT_ALL_MAC_ADDRESSES
            ] = False
            libnmstate.apply(d_state)
            assertlib.assert_state(d_state)

        assertlib.assert_absent(VETH1)
        assertlib.assert_absent(VETH1PEER)

    @pytest.mark.tier1
    def test_veth_without_peer_fails(self):
        d_state = {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.TYPE: InterfaceType.VETH,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }

        with pytest.raises(NmstateValueError):
            libnmstate.apply(d_state)

    def test_new_veth_with_ipv6_only(self):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.TYPE: InterfaceType.VETH,
                    Interface.STATE: InterfaceState.UP,
                    Veth.CONFIG_SUBTREE: {
                        Veth.PEER: VETH1PEER,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: False,
                        InterfaceIPv6.AUTOCONF: False,
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: "2001:db8:1::1",
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                    },
                }
            ]
        }
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
        finally:
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: VETH1,
                            Interface.TYPE: InterfaceType.VETH,
                            Interface.STATE: InterfaceState.ABSENT,
                        },
                        {
                            Interface.NAME: VETH1PEER,
                            Interface.TYPE: InterfaceType.VETH,
                            Interface.STATE: InterfaceState.ABSENT,
                        },
                    ]
                },
                verify_change=False,
            )

    def test_veth_invalid_mtu_smaller_than_min(self, eth1_up):
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: "eth1",
                            Interface.TYPE: InterfaceType.VETH,
                            Interface.MTU: 32,
                        },
                    ]
                }
            )

    def test_veth_invalid_mtu_bigger_than_max(self, eth1_up):
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: "eth1",
                            Interface.TYPE: InterfaceType.VETH,
                            Interface.MTU: 1500000,
                        },
                    ]
                }
            )

    def test_change_veth_with_veth_type_without_veth_conf(self, veth1_up):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.TYPE: InterfaceType.VETH,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_change_veth_with_eth_type_without_veth_conf(self, veth1_up):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: VETH1,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)


@contextmanager
def bridges_with_port():
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: "ovs-br0",
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                Bridge.CONFIG_SUBTREE: {
                    Bridge.PORT_SUBTREE: [
                        {Bridge.Port.NAME: VETH1},
                    ]
                },
            },
            {
                Interface.NAME: "br0",
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                Bridge.CONFIG_SUBTREE: {
                    Bridge.PORT_SUBTREE: [
                        {
                            Bridge.Port.NAME: VETH1PEER,
                        },
                    ]
                },
            },
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)


@contextmanager
def veth_interface_both_up(ifname, peer):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: Veth.TYPE,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: peer,
                },
            },
            {
                Interface.NAME: peer,
                Interface.TYPE: Veth.TYPE,
                Interface.STATE: InterfaceState.UP,
                Veth.CONFIG_SUBTREE: {
                    Veth.PEER: ifname,
                },
            },
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        d_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)


@pytest.fixture
def veth1_up():
    with veth_interface(VETH1, VETH1PEER):
        yield


# https://issues.redhat.com/browse/RHEL-32698
@pytest.mark.tier1
def test_show_veth_as_veth_iface_type(veth1_up):
    state = statelib.show_only((VETH1,))
    assert state[Interface.KEY][0][Interface.NAME] == VETH1
    assert state[Interface.KEY][0][Interface.TYPE] == InterfaceType.VETH
