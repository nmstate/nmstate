# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from ..testlib import cmdlib
from ..testlib import assertlib
from ..testlib.statelib import show_only


IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.1"
IPV4_NET1 = "198.51.100.0/24"
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:1::2"
IPV6_NET1 = "2001:db8:a::/64"

I32_MAX = 0x7FFFFFFF


def test_get_applied_config_for_dhcp_state_with_dhcp_enabeld_on_disk(eth1_up):
    iface_state = eth1_up[Interface.KEY][0]
    iface_name = iface_state[Interface.NAME]
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv4.method auto".split(), check=True
    )
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv6.method auto".split(), check=True
    )

    assertlib.assert_state_match({Interface.KEY: [iface_state]})


@pytest.fixture
def eth1_up_with_auto_ip(eth1_up):
    iface_name = eth1_up[Interface.KEY][0][Interface.NAME]
    iface_state = {
        Interface.NAME: iface_name,
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
    libnmstate.apply({Interface.KEY: [iface_state]})
    yield iface_state


def test_get_applied_config_for_dhcp_state_with_dhcp_disabled_on_disk(
    eth1_up_with_auto_ip,
):
    iface_state = eth1_up_with_auto_ip
    iface_name = iface_state[Interface.NAME]
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv4.method disabled".split(), check=True
    )
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv6.method disabled".split(), check=True
    )

    assertlib.assert_state_match({Interface.KEY: [iface_state]})


@pytest.fixture
def eth1_up_with_static_ip_and_route_by_iproute():
    cmdlib.exec_cmd("ip link set eth1 up".split(), check=True)
    cmdlib.exec_cmd(
        f"ip addr add {IPV4_ADDRESS1}/24 dev eth1 ".split(), check=True
    )
    cmdlib.exec_cmd(
        f"ip -6 addr add {IPV6_ADDRESS1}/64 dev eth1 ".split(), check=True
    )
    cmdlib.exec_cmd(
        f"ip route add {IPV4_NET1} via {IPV4_ADDRESS2} dev eth1 ".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"ip -6 route add {IPV6_NET1} via {IPV6_ADDRESS2} dev eth1 ".split(),
        check=True,
    )
    yield
    cmdlib.exec_cmd("nmcli c down eth1".split())
    cmdlib.exec_cmd("nmcli c del eth1".split())


def test_preserve_static_routes_created_by_iproute(
    eth1_up_with_static_ip_and_route_by_iproute,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                }
            ],
        }
    )

    assert (
        cmdlib.exec_cmd("nmcli -g ipv4.routes c show eth1".split())[1].strip()
        == "198.51.100.0/24 192.0.2.1 0 table=254"
    )
    assert (
        cmdlib.exec_cmd("nmcli -g ipv6.routes c show eth1".split())[1].strip()
        == r"2001\:db8\:a\:\:/64 2001\:db8\:1\:\:2 1024 table=254"
    )


@pytest.fixture
def eth1_up_with_nm_gateway(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
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
    cmdlib.exec_cmd(
        f"nmcli c modify eth1 ipv4.gateway {IPV4_ADDRESS2}".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"nmcli c modify eth1 ipv6.gateway {IPV6_ADDRESS2}".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        "nmcli c up eth1".split(),
        check=True,
    )
    yield


def test_switch_static_gateway_to_dhcp(eth1_up_with_nm_gateway):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
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
            ],
        }
    )

    assert (
        cmdlib.exec_cmd("nmcli -g ipv4.gateway c show eth1".split())[1].strip()
        == ""
    )
    assert (
        cmdlib.exec_cmd("nmcli -g ipv6.gateway c show eth1".split())[1].strip()
        == ""
    )


@pytest.fixture
def dummy1_with_small_dhcp_timeout():
    cmdlib.exec_cmd(
        "nmcli c add type dummy ifname dummy1 connection.id dummy1 "
        "ipv4.method auto ipv4.dhcp-timeout 5 "
        "ipv6.method auto ipv6.dhcp-timeout 5 ".split(),
        check=True,
    )
    yield
    cmdlib.exec_cmd("nmcli c del dummy1".split(), check=True)


def test_fix_dhcp_timeout_even_not_desired(dummy1_with_small_dhcp_timeout):
    iface_state = {
        Interface.NAME: "dummy1",
        Interface.DESCRIPTION: "test_only",
    }
    libnmstate.apply({Interface.KEY: [iface_state]})

    assert (
        int(
            cmdlib.exec_cmd(
                "nmcli -g ipv4.dhcp-timeout c show dummy1".split()
            )[1].strip()
        )
        == I32_MAX
    )
    assert (
        int(
            cmdlib.exec_cmd(
                "nmcli -g ipv6.dhcp-timeout c show dummy1".split()
            )[1].strip()
        )
        == I32_MAX
    )


@pytest.fixture
def eth1_up_ipv6_flushed_with_method_ignore(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: False,
                    },
                }
            ],
        }
    )

    cmdlib.exec_cmd(
        "nmcli c modify eth1 ipv6.method ignore".split(), check=True
    )
    cmdlib.exec_cmd("nmcli c up eth1".split(), check=True)
    cmdlib.exec_cmd("ip -6 addr flush dev eth1".split(), check=True)


def test_delegate_nm_ipv6_method_ignore_to_nispor(
    eth1_up_ipv6_flushed_with_method_ignore,
):
    state = show_only(("eth1",))

    assert not state[Interface.KEY][0][Interface.IPV6][InterfaceIPv6.ENABLED]
