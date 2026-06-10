# SPDX-License-Identifier: Apache-2.0

import os

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .testlib import assertlib
from .testlib import statelib
from .testlib.apply import apply_with_description
from .testlib.retry import retry_till_true_or_timeout

IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"

RETRY_TIMEOUT = 10


@pytest.fixture
def loopback_cleanup():
    yield
    apply_with_description(
        "Revert the loopback interface to default",
        {
            Interface.KEY: [
                {
                    Interface.NAME: "lo",
                    Interface.TYPE: InterfaceType.LOOPBACK,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        },
        verify_change=False,
    )


class TestLoopback:
    def test_change_loopback_mtu_and_restore_back(self, loopback_cleanup):
        cur_state = statelib.show_only(("lo",))
        origin_mtu = cur_state[Interface.KEY][0][Interface.MTU]

        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: "lo",
                    Interface.MTU: 12800,
                }
            ]
        }
        apply_with_description(
            "Set the mtu of the lookback to 12800", desired_state
        )
        assertlib.assert_state_match(desired_state)
        apply_with_description(
            "Restore the loopback interface to its default settings",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "lo",
                        Interface.TYPE: InterfaceType.LOOPBACK,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                ]
            },
        )

        # NetworkManager might take time to reset MTU of lo after we deleted
        # the profile of lo.
        def check_mtu(expected_mtu):
            state = statelib.show_only(("lo",))
            cur_mtu = state[Interface.KEY][0][Interface.MTU]
            return expected_mtu == cur_mtu

        assert retry_till_true_or_timeout(RETRY_TIMEOUT, check_mtu, origin_mtu)

    def test_add_more_ip_to_loopback(self, loopback_cleanup):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: "lo",
                    Interface.TYPE: InterfaceType.LOOPBACK,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
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
        apply_with_description(
            "Add the address 192.0.2.251/24 and 2001:db8:1::1/64 to loopback "
            "device",
            desired_state,
        )
        desired_state[Interface.KEY][0][Interface.IPV4][
            InterfaceIPv4.ADDRESS
        ].append(
            {
                InterfaceIPv4.ADDRESS_IP: "127.0.0.1",
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 8,
            }
        )
        desired_state[Interface.KEY][0][Interface.IPV6][
            InterfaceIPv6.ADDRESS
        ].append(
            {
                InterfaceIPv4.ADDRESS_IP: "::1",
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 128,
            }
        )
        assertlib.assert_state_match(desired_state)

    def test_disable_loopback_ipv4_is_rejected(self, loopback_cleanup):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: "lo",
                    Interface.TYPE: InterfaceType.LOOPBACK,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                }
            ]
        }
        with pytest.raises(
            NmstateValueError, match="cannot have IPv4 disabled"
        ):
            libnmstate.apply(desired_state)

    def test_disable_loopback_ipv6_is_rejected(self, loopback_cleanup):
        # Disabling IPv6 on loopback is only allowed when the kernel IPv6
        # stack is disabled (e.g. booted with `ipv6.disable=1`).
        if not os.path.exists("/proc/sys/net/ipv6"):
            pytest.skip("Kernel IPv6 stack is disabled")

        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: "lo",
                    Interface.TYPE: InterfaceType.LOOPBACK,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: False,
                    },
                }
            ]
        }
        with pytest.raises(
            NmstateValueError, match="cannot have IPv6 disabled"
        ):
            libnmstate.apply(desired_state)
