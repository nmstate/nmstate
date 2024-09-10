# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import Mptcp

from .testlib import assertlib
from .testlib import cmdlib


IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"


@pytest.fixture(scope="module", autouse=True)
def enable_mptcp_in_sysctl():
    ori_value = cmdlib.exec_cmd("sysctl net.mptcp.enabled".split())[1].strip()[
        -1
    ]
    cmdlib.exec_cmd("sysctl -w net.mptcp.enabled=1".split(), check=True)
    yield
    cmdlib.exec_cmd(
        f"sysctl -w net.mptcp.enabled={ori_value}".split(), check=True
    )


@pytest.fixture
def eth1_with_static_ip(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
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
    libnmstate.apply(desired_state)
    yield desired_state


@pytest.mark.parametrize(
    "mptcp_flags",
    [
        [Mptcp.FLAG_SIGNAL],
        [Mptcp.FLAG_SUBFLOW],
        [Mptcp.FLAG_BACKUP],
        [Mptcp.FLAG_FULLMESH],
        [Mptcp.FLAG_SIGNAL, Mptcp.FLAG_SUBFLOW],
        [Mptcp.FLAG_SIGNAL, Mptcp.FLAG_BACKUP],
        [Mptcp.FLAG_SUBFLOW, Mptcp.FLAG_BACKUP],
        [Mptcp.FLAG_SUBFLOW, Mptcp.FLAG_FULLMESH],
        [Mptcp.FLAG_SIGNAL, Mptcp.FLAG_SUBFLOW, Mptcp.FLAG_BACKUP],
        [
            Mptcp.FLAG_SUBFLOW,
            Mptcp.FLAG_BACKUP,
            Mptcp.FLAG_FULLMESH,
        ],
        [
            Mptcp.FLAG_FULLMESH,
            Mptcp.FLAG_SUBFLOW,
            Mptcp.FLAG_BACKUP,
        ],
    ],
    ids=[
        "signal",
        "subflow",
        "backup",
        "fullmesh",
        "signal&subflow",
        "signal&backup",
        "subflow@backup",
        "subflow@fullmesh",
        "signal@subflow@backup",
        "subflow@backup@fullmesh",
        "fullmesh@subflow@backup",
    ],
)
def test_enable_mptcp_flags_and_remove(eth1_with_static_ip, mptcp_flags):
    expected_state = eth1_with_static_ip
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.MPTCP: {
                    Mptcp.ADDRESS_FLAGS: mptcp_flags,
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    expected_state[Interface.KEY][0][Interface.MPTCP] = {
        Mptcp.ADDRESS_FLAGS: mptcp_flags
    }
    expected_state[Interface.KEY][0][Interface.IPV4][InterfaceIPv4.ADDRESS][0][
        InterfaceIPv4.MPTCP_FLAGS
    ] = mptcp_flags
    expected_state[Interface.KEY][0][Interface.IPV6][InterfaceIPv6.ADDRESS][0][
        InterfaceIPv6.MPTCP_FLAGS
    ] = mptcp_flags
    assertlib.assert_state_match(expected_state)


@pytest.mark.parametrize(
    "mptcp_flags",
    [
        [Mptcp.FLAG_SIGNAL, Mptcp.FLAG_FULLMESH],
        [Mptcp.FLAG_FULLMESH, Mptcp.FLAG_SIGNAL],
        [Mptcp.FLAG_SIGNAL, Mptcp.FLAG_SUBFLOW, Mptcp.FLAG_FULLMESH],
        [
            Mptcp.FLAG_SIGNAL,
            Mptcp.FLAG_BACKUP,
            Mptcp.FLAG_FULLMESH,
        ],
        [
            Mptcp.FLAG_FULLMESH,
            Mptcp.FLAG_SUBFLOW,
            Mptcp.FLAG_BACKUP,
            Mptcp.FLAG_SIGNAL,
        ],
    ],
    ids=[
        "signal&fullmesh",
        "fullmesh@signal",
        "signal@subflow@fullmesh",
        "signal@backup@fullmesh",
        "fullmesh@subflow@backup@signal",
    ],
)
def test_invalid_mptcp_flags(eth1_with_static_ip, mptcp_flags):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "eth1",
                        Interface.TYPE: InterfaceType.ETHERNET,
                        Interface.STATE: InterfaceState.UP,
                        Interface.MPTCP: {
                            Mptcp.ADDRESS_FLAGS: mptcp_flags,
                        },
                    }
                ]
            }
        )


# https://issues.redhat.com/browse/RHEL-38607
def test_purge_mptcp_on_auto_ip_iface_with_dhcp_server(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Interface.MPTCP: {
                        Mptcp.ADDRESS_FLAGS: [],
                    },
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                    },
                }
            ]
        }
    )
