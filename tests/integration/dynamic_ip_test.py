# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager
from copy import deepcopy
import logging
import json
from operator import itemgetter
import os
import time

import pytest

import libnmstate
from libnmstate.schema import Constants
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route

from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError
from libnmstate.iplib import is_ipv6_link_local_addr

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import bondlib
from .testlib import ifacelib
from .testlib import statelib
from .testlib.env import is_k8s
from .testlib.ifacelib import get_mac_address
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import create_bridge_subtree_state
from .testlib.bridgelib import linux_bridge
from .testlib.retry import retry_till_true_or_timeout
from .testlib.retry import retry_till_false_or_timeout
from .testlib.veth import create_veth_pair
from .testlib.veth import remove_veth_pair

ETH1 = "eth1"

DEFAULT_TIMEOUT = 20
NM_DHCP_TIMEOUT_DEFAULT = 45
# The default IPv6 RA/Autoconf timeout is 30 seconds, less than above.
NM_IPV6_AUTOCONF_TIMEOUT_DEFAULT = 30

IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV4_ADDRESS3 = "192.0.2.253"
IPV4_ADDRESS4 = "192.0.2.254"
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:2::1"
IPV6_ADDRESS3 = "2001:db8:1::3"
IPV6_ADDRESS4 = "2001:db8:1::4"
IPV4_NETWORK1 = "203.0.113.0/24"
IPV6_NETWORK1 = "2001:db8:2::/64"
IPV4_CLASSLESS_ROUTE_DST_NET1 = "198.51.100.0/24"
IPV4_CLASSLESS_ROUTE_NEXT_HOP1 = "192.0.2.1"
IPV6_CLASSLESS_ROUTE_PREFIX = "2001:db8:f"
IPV6_CLASSLESS_ROUTE_DST_NET1 = "{}::/64".format(IPV6_CLASSLESS_ROUTE_PREFIX)

TEST_BRIDGE_NIC = "brtest0"

DHCP_SRV_NIC = "dhcpsrv"
DHCP_CLI_NIC = "dhcpcli"
DHCP_SRV_NS = "nmstate_dhcp_test"
DHCP_SRV_IP4 = IPV4_ADDRESS1
DHCP_SRV_IP6 = IPV6_ADDRESS1
DHCP_SRV_IP6_2 = "{}::1".format(IPV6_CLASSLESS_ROUTE_PREFIX)
DHCP_SRV_IP4_PREFIX = "192.0.2"
DHCP_SRV_IP6_PREFIX = "2001:db8:1"
DHCP_SRV_IP6_NETWORK = "{}::/64".format(DHCP_SRV_IP6_PREFIX)

IPV6_DEFAULT_GATEWAY = "::/0"
IPV4_DEFAULT_GATEWAY = "0.0.0.0/0"

IPV4_DNS_NAMESERVER = "8.8.8.8"
IPV6_DNS_NAMESERVER = "2001:4860:4860::8888"
IPV6_DNS_NAMESERVER_LOCAL = f"fe80::deef:1%{DHCP_CLI_NIC}"
EXAMPLE_SEARCHES = ["example.org", "example.com"]

DNSMASQ_CONF_STR = """
leasefile-ro
interface={iface}
dhcp-range={ipv4_prefix}.200,{ipv4_prefix}.250,255.255.255.0,48h
enable-ra
dhcp-range={ipv6_prefix}::100,{ipv6_prefix}::fff,ra-names,slaac,64,480h
dhcp-range={ipv6_classless_route}::100,{ipv6_classless_route}::fff,static
dhcp-option=option:classless-static-route,{classless_rt},{classless_rt_dst}
dhcp-option=option:dns-server,{v4_dns_server}
""".format(
    **{
        "iface": DHCP_SRV_NIC,
        "ipv4_prefix": DHCP_SRV_IP4_PREFIX,
        "ipv6_prefix": DHCP_SRV_IP6_PREFIX,
        "classless_rt": IPV4_CLASSLESS_ROUTE_DST_NET1,
        "classless_rt_dst": IPV4_CLASSLESS_ROUTE_NEXT_HOP1,
        "v4_dns_server": DHCP_SRV_IP4,
        "ipv6_classless_route": IPV6_CLASSLESS_ROUTE_PREFIX,
    }
)

DNSMASQ_CONF_PATH = "/etc/dnsmasq.d/nmstate.conf"
# Docker does not allow NetworkManager to edit /etc/resolv.conf.
# Have to read NetworkManager internal resolv.conf
RESOLV_CONF_PATH = "/var/run/NetworkManager/resolv.conf"

TEST_IPV6_TOKEN = "::fac"
TEST_IPV6_TOKEN_IPV4_COMPAT = "::0.0.15.172"
TEST_IPV6_TOKEN2 = "::fad"

parametrize_ip_ver = pytest.mark.parametrize(
    "ip_ver",
    [(Interface.IPV4,), (Interface.IPV6,), (Interface.IPV4, Interface.IPV6)],
    ids=["ipv4", "ipv6", "ipv4&6"],
)


@pytest.fixture(scope="module")
def dhcp_env():
    try:
        create_veth_pair(DHCP_CLI_NIC, DHCP_SRV_NIC, DHCP_SRV_NS)
        _setup_dhcp_nics()

        with open(DNSMASQ_CONF_PATH, "w") as fd:
            fd.write(DNSMASQ_CONF_STR)
        cmdlib.exec_cmd(
            f"ip netns exec {DHCP_SRV_NS} "
            f"dnsmasq -C {DNSMASQ_CONF_PATH}".split(),
            check=True,
        )

        yield
    finally:
        _clean_up()


@pytest.fixture
def dhcpcli_up(dhcp_env):
    with ifacelib.iface_up(DHCP_CLI_NIC) as ifstate:
        yield ifstate


@pytest.fixture
def dhcpcli_up_with_dynamic_ip(dhcp_env):
    with iface_with_dynamic_ip_up(DHCP_CLI_NIC) as ifstate:
        yield ifstate


@contextmanager
def iface_with_dynamic_ip_up(ifname):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: _create_ipv4_state(enabled=True, dhcp=True),
                Interface.IPV6: _create_ipv6_state(
                    enabled=True, dhcp=True, autoconf=True
                ),
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assert _poll(_has_ipv4_dhcp_gateway)
        assert _poll(_has_dhcpv4_addr)
        assert _poll(_has_ipv6_auto_gateway)
        assert _poll(_has_dhcpv6_addr)
        yield statelib.show_only((ifname,))
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ifname,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )


@pytest.mark.tier1
def test_ipv4_dhcp(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)

    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)


def test_ipv6_dhcp_only(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_nameserver)
    assert _poll(_has_dhcpv6_addr)
    # DHCPv6 does not provide routes
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()


@pytest.mark.tier1
def test_ipv6_dhcp_and_autoconf(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_extra_route)
    assert _poll(_has_ipv6_auto_nameserver)


@pytest.mark.tier1
def test_static_ip_with_auto_ip_enabled(dhcpcli_up):
    ipv4_state = _create_ipv4_state(enabled=True, dhcp=True)
    ipv4_state[InterfaceIPv4.ADDRESS] = [
        create_ipv4_address_state(IPV4_ADDRESS3, 24),
        # Nmstate is supposed to ignore IP address with lifetime when DHCPv4
        # is enabled
        create_ipv4_address_state(
            IPV4_ADDRESS4, 24, valid_left="30sec", preferred_left="30sec"
        ),
    ]
    ipv6_state = _create_ipv6_state(enabled=True, dhcp=True, autoconf=True)
    ipv6_state[InterfaceIPv6.ADDRESS] = [
        create_ipv6_address_state(IPV6_ADDRESS3, 64),
        # Nmstate is supposed to ignore IP address with lifetime when
        # autoconf/DHCPv6 is enabled
        create_ipv6_address_state(
            IPV6_ADDRESS4, 64, valid_left="30sec", preferred_left="30sec"
        ),
    ]

    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: ipv4_state,
                Interface.IPV6: ipv6_state,
            }
        ]
    }

    libnmstate.apply(desired_state)

    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)
    assert _poll(_has_dhcpv4_addr)
    assert _poll(_has_dhcpv6_addr)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_extra_route)
    assert _poll(_has_ipv6_auto_nameserver)
    ip4_addr_output = cmdlib.exec_cmd(
        f"ip -4 addr show dev {DHCP_CLI_NIC}".split(), check=True
    )[1]
    ip6_addr_output = cmdlib.exec_cmd(
        f"ip -6 addr show dev {DHCP_CLI_NIC}".split(), check=True
    )[1]
    assert f"{IPV4_ADDRESS3}/24" in ip4_addr_output
    assert f"{IPV4_ADDRESS4}/24" not in ip4_addr_output
    assert f"{IPV6_ADDRESS3}/64" in ip6_addr_output
    assert f"{IPV6_ADDRESS4}/64" not in ip6_addr_output
    assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=AssertionError,
    strict=False,
)
def test_ipv4_dhcp_on_bond(dhcpcli_up):
    ipv4_state = {Interface.IPV4: _create_ipv4_state(enabled=True, dhcp=True)}
    with bondlib.bond_interface(
        "bond99", port=[DHCP_CLI_NIC], extra_iface_state=ipv4_state
    ) as desired_state:
        assertlib.assert_state_match(desired_state)


def test_ipv4_dhcp_ignore_gateway(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True, auto_gateway=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_classless_route)
    assert not _has_ipv4_dhcp_gateway()


def test_ipv4_dhcp_ignore_dns(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True, auto_dns=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)
    assert not _has_ipv4_dhcp_nameserver()


def test_ipv4_dhcp_ignore_routes(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True, auto_routes=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_nameserver)
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv4_dhcp_set_table_id(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True, table_id=100
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv6_dhcp_set_table_id_without_autoconf(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, table_id=100
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv6_dhcp_set_table_id_with_autoconf(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True, table_id=100
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv6_dhcp_and_autoconf_ignore_gateway(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True, auto_gateway=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_extra_route)
    assert _poll(_has_ipv6_auto_nameserver)
    assert not _has_ipv6_auto_gateway()


def test_ipv6_dhcp_and_autoconf_ignore_dns(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True, auto_dns=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_extra_route)
    assert not _has_ipv6_auto_nameserver()


def test_ipv6_dhcp_and_autoconf_ignore_routes(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True, auto_routes=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_nameserver)
    assert not _has_ipv6_auto_gateway()
    assert not _has_ipv6_auto_extra_route()


def test_ipv4_dhcp_off_and_option_on(dhcpcli_up):
    """
    AUTO_ROUTES, AUTO_DNS and AUTO_GATEWAY should be silently ignored when
    DHCP is disabled.
    """
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    ipv4_state = _create_ipv4_state(
        enabled=True,
        dhcp=False,
        auto_dns=False,
        auto_gateway=False,
        auto_routes=False,
    )
    ipv4_state[InterfaceIPv4.ADDRESS] = [
        create_ipv4_address_state(IPV4_ADDRESS2, 24),
    ]

    dhcp_cli_desired_state[Interface.IPV4] = ipv4_state

    libnmstate.apply(desired_state)

    current_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_current_state = current_state[Interface.KEY][0]
    ipv4_current_state = dhcp_cli_current_state[Interface.IPV4]
    assert not ipv4_current_state[InterfaceIPv4.DHCP]
    assert InterfaceIPv4.AUTO_ROUTES not in ipv4_current_state
    assert InterfaceIPv4.AUTO_DNS not in ipv4_current_state
    assert InterfaceIPv4.AUTO_GATEWAY not in ipv4_current_state
    assert not _poll_till_not(_has_ipv4_dhcp_nameserver)
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_off_and_option_on(dhcpcli_up):
    """
    AUTO_ROUTES, AUTO_DNS and AUTO_GATEWAY should be silently ignored when
    DHCP is disabled.
    """
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    ipv6_state = _create_ipv6_state(
        enabled=True,
        dhcp=False,
        autoconf=False,
        auto_dns=False,
        auto_gateway=False,
        auto_routes=False,
    )
    ipv6_state[InterfaceIPv6.ADDRESS] = [
        create_ipv6_address_state(IPV6_ADDRESS2, 64),
    ]
    dhcp_cli_desired_state[Interface.IPV6] = ipv6_state

    libnmstate.apply(desired_state)

    current_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_current_state = current_state[Interface.KEY][0]
    ipv6_current_state = dhcp_cli_current_state[Interface.IPV6]
    assert not ipv6_current_state[InterfaceIPv6.DHCP]
    assert InterfaceIPv6.AUTO_ROUTES not in ipv6_current_state
    assert InterfaceIPv6.AUTO_DNS not in ipv6_current_state
    assert InterfaceIPv6.AUTO_GATEWAY not in ipv6_current_state
    assert not _poll_till_not(_has_ipv6_auto_gateway)
    assert not _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def test_ipv4_dhcp_switch_on_to_off(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)

    # disable dhcp and make sure dns, route, gone.
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=False
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    # When converting from DHCP to static without address mentioned,
    # nmstate should convert existing dynamic IP addresses to static
    assert _poll(_has_dhcpv4_addr)
    assert not _poll_till_not(_has_ipv4_dhcp_nameserver)
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_switch_on_to_off(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_extra_route)
    assert _poll(_has_ipv6_auto_nameserver)

    # disable dhcp and make sure dns, route, gone.
    desired_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(enabled=True)

    print(desired_state)
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert not _poll_till_not(_has_ipv6_auto_gateway)
    assert not _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


@pytest.mark.tier1
def test_dhcp_on_bridge0(dhcpcli_up_with_dynamic_ip):
    """
    Test dynamic IPv4 & IPv6 addresses over a Linux bridge interface.

    Several checks have been ecooperated in the test due to the high time cost.
    The dynamic IP over the bridge includes the follwing checks:
        - The dynamic settings have been applied.
        - IPv4 and IPv6 addresses have been provided by the server.
        - IPv4 addresses are identical to the original ones which existed on
        the nic (dhcpcli interface).
        - IPv6 addresses are identical to the original ones which existed on
        the nic (dhcpcli interface).
    """
    origin_port_state = dhcpcli_up_with_dynamic_ip

    port_name = origin_port_state[Interface.KEY][0][Interface.NAME]

    bridge_state = create_bridge_subtree_state()
    bridge_state = add_port_to_bridge(bridge_state, port_name)

    bridge_iface_state = {
        Interface.IPV4: _create_ipv4_state(enabled=True, dhcp=True),
        Interface.IPV6: _create_ipv6_state(
            enabled=True, dhcp=True, autoconf=True
        ),
        Interface.MAC: get_mac_address(DHCP_CLI_NIC),
    }
    bridge_name = TEST_BRIDGE_NIC
    with linux_bridge(bridge_name, bridge_state, bridge_iface_state) as state:
        assertlib.assert_state_match(state)

        assert _poll(_has_dhcpv4_addr, nic=TEST_BRIDGE_NIC)
        assert _poll(_has_ipv4_dhcp_gateway, nic=TEST_BRIDGE_NIC)
        assert _poll(_has_dhcpv6_addr, nic=TEST_BRIDGE_NIC)
        assert _poll(_has_ipv6_auto_gateway, nic=TEST_BRIDGE_NIC)
        new_bridge_state = statelib.show_only((bridge_name,))

    new_ipv4_state = new_bridge_state[Interface.KEY][0][Interface.IPV4]
    new_ipv6_state = new_bridge_state[Interface.KEY][0][Interface.IPV6]
    assert new_ipv4_state[InterfaceIPv4.ADDRESS]
    assert len(new_ipv6_state[InterfaceIPv6.ADDRESS]) > 1

    origin_ipv4_state = origin_port_state[Interface.KEY][0][Interface.IPV4]
    origin_ipv6_state = origin_port_state[Interface.KEY][0][Interface.IPV6]
    _sort_ip_addresses(origin_ipv4_state[InterfaceIP.ADDRESS])
    _sort_ip_addresses(origin_ipv6_state[InterfaceIP.ADDRESS])
    _sort_ip_addresses(new_ipv4_state[InterfaceIP.ADDRESS])
    _sort_ip_addresses(new_ipv6_state[InterfaceIP.ADDRESS])
    _remove_ip_lifetime(origin_ipv4_state[InterfaceIP.ADDRESS])
    _remove_ip_lifetime(origin_ipv6_state[InterfaceIP.ADDRESS])
    _remove_ip_lifetime(new_ipv4_state[InterfaceIP.ADDRESS])
    _remove_ip_lifetime(new_ipv6_state[InterfaceIP.ADDRESS])
    assert origin_ipv4_state == new_ipv4_state
    assert origin_ipv6_state == new_ipv6_state


@pytest.mark.tier1
def test_port_ipaddr_learned_via_dhcp_added_as_static_to_linux_bridge(
    dhcpcli_up,
):
    dhcpcli_up[Interface.KEY][0][Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )

    libnmstate.apply(dhcpcli_up)

    assert _poll(_has_dhcpv4_addr)

    port_ifname = dhcpcli_up[Interface.KEY][0][Interface.NAME]
    port_state = statelib.show_only((port_ifname,))
    port_iface_state = port_state[Interface.KEY][0]
    dhcpcli_ip = port_iface_state[Interface.IPV4][InterfaceIPv4.ADDRESS]

    bridge_state = add_port_to_bridge(
        create_bridge_subtree_state(), port_ifname
    )

    ipv4_state = _create_ipv4_state(enabled=True, dhcp=False)
    ipv4_state[InterfaceIPv4.ADDRESS] = dhcpcli_ip
    _remove_ip_lifetime(ipv4_state[InterfaceIPv4.ADDRESS])
    with linux_bridge(
        TEST_BRIDGE_NIC,
        bridge_state,
        extra_iface_state={Interface.IPV4: ipv4_state},
        create=False,
    ) as state:
        state[Interface.KEY].append(
            {
                Interface.NAME: port_ifname,
                Interface.IPV4: _create_ipv4_state(enabled=False),
                Interface.IPV6: _create_ipv6_state(enabled=False),
            }
        )
        libnmstate.apply(state)

        assertlib.assert_state_match(state)


@pytest.mark.xfail(raises=NmstateNotImplementedError, strict=True)
def test_ipv6_autoconf_only(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, autoconf=True
    )

    libnmstate.apply(desired_state)


def _setup_dhcp_nics():
    cmdlib.exec_cmd(
        f"ip netns exec {DHCP_SRV_NS} "
        f"ip addr add {DHCP_SRV_IP4}/24 dev {DHCP_SRV_NIC}".split(),
        check=True,
    )
    # This stop dhcp server NIC get another IPv6 address from dnsmasq.
    cmdlib.exec_cmd(
        f"ip netns exec {DHCP_SRV_NS} "
        f"sysctl -w net.ipv6.conf.{DHCP_SRV_NIC}.accept_ra=0".split(),
        check=True,
    )

    cmdlib.exec_cmd(
        f"ip netns exec {DHCP_SRV_NS} "
        f"ip addr add {DHCP_SRV_IP6}/64 dev {DHCP_SRV_NIC}".split(),
        check=True,
    )

    cmdlib.exec_cmd(
        f"ip netns exec {DHCP_SRV_NS} "
        f"ip addr add {DHCP_SRV_IP6_2}/64 dev {DHCP_SRV_NIC}".split(),
        check=True,
    )


def _clean_up():
    dnsmasq_pid = cmdlib.exec_cmd(["pidof", "dnsmasq"])[1]
    cmdlib.exec_cmd(["kill", dnsmasq_pid.strip()])
    remove_veth_pair(DHCP_CLI_NIC, DHCP_SRV_NS)
    try:
        os.unlink(DNSMASQ_CONF_PATH)
    except (FileNotFoundError, OSError):
        pass


def _get_nameservers():
    """
    Return a list of name server string configured in RESOLV_CONF_PATH.
    """
    running_ns = (
        libnmstate.show()
        .get(Constants.DNS, {})
        .get(DNS.RUNNING, {})
        .get(DNS.SERVER, [])
    )
    logging.debug("Current running DNS: {}".format(running_ns))
    return running_ns


def _get_running_routes():
    """
    return a list of running routes
    """
    running_routes = (
        libnmstate.show().get(Constants.ROUTES, {}).get(Route.RUNNING, [])
    )
    logging.debug("Current running routes: {}".format(running_routes))
    return running_routes


def _poll(func, *args, **kwargs):
    return retry_till_true_or_timeout(DEFAULT_TIMEOUT, func, *args, **kwargs)


def _poll_till_not(func, *args, **kwargs):
    return retry_till_false_or_timeout(DEFAULT_TIMEOUT, func, *args, **kwargs)


def _has_ipv6_auto_gateway(nic=DHCP_CLI_NIC):
    routes = _get_running_routes()
    for route in routes:
        if (
            route[Route.DESTINATION] == IPV6_DEFAULT_GATEWAY
            and route[Route.NEXT_HOP_INTERFACE] == nic
        ):
            return True
    return False


def _has_ipv6_auto_extra_route():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[Route.DESTINATION] == IPV6_CLASSLESS_ROUTE_DST_NET1
            and route[Route.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        ):
            return True
    return False


def _has_ipv6_auto_nameserver():
    return DHCP_SRV_IP6 in _get_nameservers()


def _has_ipv4_dhcp_nameserver():
    return DHCP_SRV_IP4 in _get_nameservers()


def _has_ipv4_dhcp_gateway(nic=DHCP_CLI_NIC):
    routes = _get_running_routes()
    for route in routes:
        if (
            route[Route.DESTINATION] == IPV4_DEFAULT_GATEWAY
            and route[Route.NEXT_HOP_INTERFACE] == nic
        ):
            return True
    return False


def _has_ipv4_classless_route():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[Route.DESTINATION] == IPV4_CLASSLESS_ROUTE_DST_NET1
            and route[Route.NEXT_HOP_ADDRESS] == IPV4_CLASSLESS_ROUTE_NEXT_HOP1
            and route[Route.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        ):
            return True
    return False


def _has_dhcpv6_addr(nic=DHCP_CLI_NIC):
    current_state = statelib.show_only((nic,))[Interface.KEY][0]
    has_dhcp_ip_addr = False
    addrs = current_state[Interface.IPV6].get(InterfaceIPv6.ADDRESS, [])
    logging.debug("Current IPv6 address of {}: {}".format(nic, addrs))
    for addr in addrs:
        if (
            addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH] == 128
            and DHCP_SRV_IP6_PREFIX in addr[InterfaceIPv6.ADDRESS_IP]
        ):
            has_dhcp_ip_addr = True
            break
    return has_dhcp_ip_addr


def _has_dhcpv4_addr(nic=DHCP_CLI_NIC):
    current_state = statelib.show_only((nic,))[Interface.KEY][0]
    has_dhcp_ip_addr = False
    addrs = current_state[Interface.IPV4].get(InterfaceIPv4.ADDRESS, [])
    logging.debug("Current IPv4 address of {}: {}".format(nic, addrs))
    for addr in addrs:
        if (
            addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH] == 24
            and DHCP_SRV_IP4_PREFIX in addr[InterfaceIPv4.ADDRESS_IP]
        ):
            has_dhcp_ip_addr = True
            break
    return has_dhcp_ip_addr


def _create_ipv4_state(
    enabled,
    dhcp=False,
    auto_dns=True,
    auto_gateway=True,
    auto_routes=True,
    table_id=0,
):
    state = {
        InterfaceIPv4.ENABLED: enabled,
        InterfaceIPv4.DHCP: dhcp,
        InterfaceIPv4.AUTO_DNS: auto_dns,
        InterfaceIPv4.AUTO_GATEWAY: auto_gateway,
        InterfaceIPv4.AUTO_ROUTES: auto_routes,
    }
    if dhcp:
        state[InterfaceIPv4.AUTO_ROUTE_TABLE_ID] = table_id

    return state


def _create_ipv6_state(
    enabled,
    dhcp=False,
    autoconf=False,
    auto_dns=True,
    auto_gateway=True,
    auto_routes=True,
    table_id=0,
):
    state = {
        InterfaceIPv6.ENABLED: enabled,
        InterfaceIPv6.DHCP: dhcp,
        InterfaceIPv6.AUTOCONF: autoconf,
        InterfaceIPv6.AUTO_DNS: auto_dns,
        InterfaceIPv6.AUTO_GATEWAY: auto_gateway,
        InterfaceIPv6.AUTO_ROUTES: auto_routes,
    }

    if dhcp or autoconf:
        state[InterfaceIPv6.AUTO_ROUTE_TABLE_ID] = table_id

    return state


def create_ipv4_address_state(
    address, prefix_length, valid_left=None, preferred_left=None
):
    return {
        InterfaceIPv4.ADDRESS_IP: address,
        InterfaceIPv4.ADDRESS_PREFIX_LENGTH: prefix_length,
        InterfaceIPv4.ADDRESS_VALID_LEFT: valid_left,
        InterfaceIPv4.ADDRESS_PREFERRED_LEFT: preferred_left,
    }


def create_ipv6_address_state(
    address, prefix_length, valid_left=None, preferred_left=None
):
    return {
        InterfaceIPv6.ADDRESS_IP: address,
        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: prefix_length,
        InterfaceIPv6.ADDRESS_VALID_LEFT: valid_left,
        InterfaceIPv6.ADDRESS_PREFERRED_LEFT: preferred_left,
    }


@pytest.fixture(scope="function")
def dummy00():
    ifstate = {
        Interface.NAME: "dummy00",
        Interface.TYPE: InterfaceType.DUMMY,
        Interface.STATE: InterfaceState.UP,
    }
    libnmstate.apply({Interface.KEY: [ifstate]})
    yield ifstate
    ifstate[Interface.STATE] = InterfaceState.ABSENT
    libnmstate.apply({Interface.KEY: [ifstate]}, verify_change=False)


@parametrize_ip_ver
def test_activate_dummy_without_dhcp_service(ip_ver, dummy00):
    ifstate = dummy00
    if Interface.IPV4 in ip_ver:
        ifstate[Interface.IPV4] = _create_ipv4_state(enabled=True, dhcp=True)
    if Interface.IPV6 in ip_ver:
        ifstate[Interface.IPV6] = _create_ipv6_state(
            enabled=True, dhcp=True, autoconf=True
        )
    libnmstate.apply({Interface.KEY: [ifstate]})


@pytest.mark.tier1
def test_dummy_disable_ip_stack_with_on_going_dhcp(dummy00):
    ifstate = dummy00
    ifstate[Interface.IPV4] = _create_ipv4_state(enabled=True, dhcp=True)
    ifstate[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )
    libnmstate.apply({Interface.KEY: [ifstate]})
    ifstate[Interface.IPV4] = _create_ipv4_state(enabled=False)
    ifstate[Interface.IPV6] = _create_ipv6_state(enabled=False)
    libnmstate.apply({Interface.KEY: [ifstate]})


def test_dhcp4_with_static_ipv6(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )
    dhcp_cli_desired_state[Interface.IPV6] = {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        ],
    }

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)


def test_dhcp6_and_autoconf_with_static_ipv4(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )
    dhcp_cli_desired_state[Interface.IPV4] = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS2,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
    }

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)

    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_dhcpv6_addr)


@pytest.fixture(scope="function")
def dhcpcli_up_with_static_ip(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS2,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
    }
    dhcp_cli_desired_state[Interface.IPV6] = {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        ],
    }

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    yield desired_state


@pytest.mark.tier1
def test_change_static_to_dhcp4_with_disabled_ipv6(dhcpcli_up_with_static_ip):
    desired_state = dhcpcli_up_with_static_ip
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )
    dhcp_cli_desired_state[Interface.IPV6] = {InterfaceIPv6.ENABLED: False}

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)


@pytest.mark.tier1
def test_change_static_to_dhcp6_autoconf_with_disabled_ipv4(
    dhcpcli_up_with_static_ip,
):
    desired_state = dhcpcli_up_with_static_ip
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]

    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )
    dhcp_cli_desired_state[Interface.IPV4] = {InterfaceIPv4.ENABLED: False}

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert _poll(_has_dhcpv6_addr)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_nameserver)
    assert _poll(_has_ipv6_auto_extra_route)


@pytest.mark.tier1
@pytest.mark.slow
@parametrize_ip_ver
def test_dummy_existance_after_dhcp_timeout(ip_ver, dummy00):
    ifstate = dummy00
    if Interface.IPV4 in ip_ver:
        ifstate[Interface.IPV4] = _create_ipv4_state(enabled=True, dhcp=True)
    if Interface.IPV6 in ip_ver:
        ifstate[Interface.IPV6] = _create_ipv6_state(
            enabled=True, dhcp=True, autoconf=False
        )
    libnmstate.apply({Interface.KEY: [ifstate]})
    time.sleep(NM_DHCP_TIMEOUT_DEFAULT + 1)
    # NetworkManager by default remove virtual interface after DHCP timeout
    assertlib.assert_state({Interface.KEY: [ifstate]})


@pytest.mark.tier1
@pytest.mark.slow
def test_dummy_existance_after_ipv6_autoconf_timeout(dummy00):
    ifstate = dummy00
    ifstate[Interface.IPV4] = _create_ipv4_state(enabled=False)
    ifstate[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )
    libnmstate.apply({Interface.KEY: [ifstate]})
    time.sleep(NM_IPV6_AUTOCONF_TIMEOUT_DEFAULT + 1)

    # NetworkManager by default remove virtual interface after autoconf timeout
    # According to RFC 4861, autoconf(IPv6-RA) will instruct client to do
    # DHCPv6 or not. With autoconf timeout, DHCPv6 will not start.
    assertlib.assert_state({Interface.KEY: [ifstate]})


@pytest.fixture(scope="function")
def dhcpcli_up_with_static_ip_and_route(dhcpcli_up_with_static_ip):
    desired_state = dhcpcli_up_with_static_ip
    desired_state[Route.KEY] = {
        Route.CONFIG: [
            {
                Route.DESTINATION: IPV4_DEFAULT_GATEWAY,
                Route.NEXT_HOP_ADDRESS: DHCP_SRV_IP4,
                Route.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
            {
                Route.DESTINATION: IPV4_NETWORK1,
                Route.NEXT_HOP_ADDRESS: DHCP_SRV_IP4,
                Route.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
            {
                Route.DESTINATION: IPV6_DEFAULT_GATEWAY,
                Route.NEXT_HOP_ADDRESS: IPV6_ADDRESS3,
                Route.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
            {
                Route.DESTINATION: IPV6_NETWORK1,
                Route.NEXT_HOP_ADDRESS: IPV6_ADDRESS3,
                Route.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
        ]
    }

    libnmstate.apply(desired_state)
    yield desired_state


@pytest.mark.tier1
def test_static_ip_with_routes_switch_back_to_dynamic(
    dhcpcli_up_with_static_ip_and_route,
):
    desired_state = dhcpcli_up_with_static_ip_and_route
    desired_state.pop(Route.KEY)
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)

    assert _poll(_has_ipv4_dhcp_nameserver)
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv4_classless_route)
    assert _poll(_has_dhcpv4_addr)
    assert _poll(_has_dhcpv6_addr)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_extra_route)
    assert _poll(_has_ipv6_auto_nameserver)

    current_config_routes = [
        route
        for route in libnmstate.show()[Route.KEY][Route.CONFIG]
        if route[Route.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
    ]
    assert not current_config_routes


@pytest.fixture(scope="function")
def eth1_with_dhcp6_no_dhcp_server():
    # Cannot depend on eth1_up fixture as the reproducer requires the
    # veth profile been created with DHCPv6 enabled.
    iface_state = {
        Interface.NAME: ETH1,
        Interface.TYPE: InterfaceType.ETHERNET,
        Interface.STATE: InterfaceState.UP,
    }
    iface_state[Interface.IPV4] = _create_ipv4_state(enabled=False)
    iface_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=False
    )
    libnmstate.apply({Interface.KEY: [iface_state]})
    try:
        yield iface_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ETH1,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
            verify_change=False,
        )


def test_switch_from_dynamic_ip_without_dhcp_srv_to_static_ipv6(
    eth1_with_dhcp6_no_dhcp_server,
):
    iface_state = eth1_with_dhcp6_no_dhcp_server
    iface_state[Interface.IPV4] = {InterfaceIPv4.ENABLED: False}
    iface_state[Interface.IPV6] = {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.AUTOCONF: False,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        ],
    }
    libnmstate.apply({Interface.KEY: [iface_state]})
    assertlib.assert_state_match({Interface.KEY: [iface_state]})


@pytest.fixture
def dhcpcli_up_with_dns_cleanup(dhcpcli_up):
    yield dhcpcli_up
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


def test_dynamic_ip_with_static_dns(dhcpcli_up_with_dns_cleanup, clean_state):
    iface_state = {
        Interface.NAME: DHCP_CLI_NIC,
        Interface.STATE: InterfaceState.UP,
        Interface.IPV4: _create_ipv4_state(
            enabled=True, dhcp=True, auto_dns=False
        ),
        Interface.IPV6: _create_ipv6_state(
            enabled=True, dhcp=True, autoconf=True, auto_dns=False
        ),
    }
    dns_config = {
        DNS.CONFIG: {
            DNS.SERVER: [IPV6_DNS_NAMESERVER, IPV4_DNS_NAMESERVER],
            DNS.SEARCH: EXAMPLE_SEARCHES,
        }
    }
    desired_state = {Interface.KEY: [iface_state], DNS.KEY: dns_config}

    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_dhcpv4_addr)
    assert _poll(_has_dhcpv6_addr)
    assert not _has_ipv4_dhcp_nameserver()
    assert not _has_ipv6_auto_nameserver()
    new_state = libnmstate.show()
    assert dns_config[DNS.CONFIG] == new_state[DNS.KEY][DNS.CONFIG]
    assert dns_config[DNS.CONFIG] == new_state[DNS.KEY][DNS.RUNNING]


@pytest.fixture(scope="function")
def clean_state():
    current_state = libnmstate.show()
    desired_state = deepcopy(current_state)
    for iface_state in desired_state[Interface.KEY]:
        if iface_state[Interface.IPV4][InterfaceIPv4.ENABLED]:
            iface_state[Interface.IPV4][InterfaceIPv4.AUTO_DNS] = False
            iface_state[Interface.IPV4][InterfaceIPv4.AUTO_ROUTES] = False
        if iface_state[Interface.IPV6][InterfaceIPv6.ENABLED]:
            iface_state[Interface.IPV6][InterfaceIPv6.AUTO_DNS] = False
            iface_state[Interface.IPV6][InterfaceIPv6.AUTO_ROUTES] = False

    libnmstate.apply(desired_state)
    try:
        yield
    finally:
        libnmstate.apply(current_state)


def _sort_ip_addresses(addresses):
    addresses.sort(key=itemgetter(InterfaceIP.ADDRESS_IP))


def _remove_ip_lifetime(addresses):
    for addr in addresses:
        addr.pop(InterfaceIP.ADDRESS_VALID_LEFT, None)
        addr.pop(InterfaceIP.ADDRESS_PREFERRED_LEFT, None)


def test_enable_dhcp_with_no_server(dummy00):
    iface_info = dummy00
    iface_info[Interface.IPV4] = _create_ipv4_state(enabled=True, dhcp=True)
    iface_info[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=False
    )
    desired_state = {Interface.KEY: [iface_info]}
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_show_running_config_does_not_include_auto_config(
    dhcpcli_up_with_dynamic_ip,
):
    running_config = libnmstate.show_running_config()
    dhcpcli_iface_config = None
    for iface_config in running_config[Interface.KEY]:
        if iface_config[Interface.NAME] == DHCP_CLI_NIC:
            dhcpcli_iface_config = iface_config
            break
    nmstatectl_output = cmdlib.exec_cmd(
        ["nmstatectl", "show", "-r", DHCP_CLI_NIC, "--json"]
    )[1]
    nmstatectl_iface_state = json.loads(nmstatectl_output)[Interface.KEY][0]

    for iface_config in (dhcpcli_iface_config, nmstatectl_iface_state):
        assert iface_config[Interface.IPV4][InterfaceIPv4.DHCP]
        assert iface_config[Interface.IPV6][InterfaceIPv6.DHCP]
        assert iface_config[Interface.IPV6][InterfaceIPv6.AUTOCONF]
        assert not iface_config[Interface.IPV4][InterfaceIPv4.ADDRESS]
        ipv6_addresses = iface_config[Interface.IPV6][InterfaceIPv6.ADDRESS]
        assert len(ipv6_addresses) == 1
        assert is_ipv6_link_local_addr(
            ipv6_addresses[0][InterfaceIPv6.ADDRESS_IP],
            ipv6_addresses[0][InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
        )
    assert DHCP_SRV_IP4 not in running_config[DNS.KEY][DNS.CONFIG]
    assert DHCP_SRV_IP6 not in running_config[DNS.KEY][DNS.CONFIG]
    assert not any(
        rt
        for rt in running_config[Route.KEY][Route.CONFIG]
        if rt[Route.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
    )


@pytest.mark.parametrize(
    "duid_type",
    ["llt", "ll", "0f:66:55:BC:73:4D"],
    ids=["llt", "ll", "raw"],
)
def test_dhcpv6_duid(dhcpcli_up_with_dynamic_ip, duid_type):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.DHCP_DUID: duid_type,
                    },
                }
            ]
        }
    )


@pytest.mark.parametrize(
    "client_id_type",
    ["ll", "iaid+duid", "0f:66:55:BC:73:4D"],
    ids=["ll", "iaid+duid", "raw"],
)
def test_dhcpv4_client_id(dhcpcli_up_with_dynamic_ip, client_id_type):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                        InterfaceIPv4.DHCP_CLIENT_ID: client_id_type,
                    },
                }
            ]
        }
    )


@pytest.mark.parametrize(
    "addr_gen_mode",
    [
        InterfaceIPv6.ADDR_GEN_MODE_EUI64,
        InterfaceIPv6.ADDR_GEN_MODE_STABLE_PRIVACY,
    ],
)
def test_auto6_addr_gen_mode(dhcpcli_up_with_dynamic_ip, addr_gen_mode):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.ADDR_GEN_MODE: addr_gen_mode,
                    },
                }
            ]
        }
    )


def test_hide_addr_gen_mode_if_ipv6_disabled(dhcpcli_up_with_dynamic_ip):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: False,
                    },
                }
            ]
        }
    )
    current_state = statelib.show_only((DHCP_CLI_NIC,))
    assert (
        InterfaceIPv6.ADDR_GEN_MODE
        not in current_state[Interface.KEY][0][Interface.IPV6]
    )


@pytest.mark.tier1
@pytest.mark.parametrize(
    "wait_ip",
    [
        "any",
        "ipv4",
        "ipv6",
        "ipv4+ipv6",
    ],
)
def test_wait_ip(eth1_up, wait_ip):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.WAIT_IP: wait_ip,
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


def test_auto_route_metric(dhcpcli_up_with_dynamic_ip):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                        InterfaceIPv4.AUTO_ROUTE_METRIC: 901,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.AUTO_ROUTE_METRIC: 902,
                    },
                }
            ],
        }
    )
    _poll(_has_auto_route_with_desired_metric, family=4, metric=901)
    _poll(_has_auto_route_with_desired_metric, family=6, metric=902)


def _has_auto_route_with_desired_metric(family, metric):
    output = cmdlib.exec_cmd(
        f"ip -{family} -j route show proto dhcp".split(), check=True
    )[1]
    ip_routes = json.loads(output)
    if ip_routes:
        return ip_routes[0].get("metric") == 901
    else:
        return False


@pytest.mark.tier1
def test_ipv6_link_local_dns_srv(dhcpcli_up_with_dynamic_ip):
    libnmstate.apply(
        {
            DNS.KEY: {
                DNS.CONFIG: {
                    DNS.SERVER: [
                        IPV6_DNS_NAMESERVER,
                        IPV6_DNS_NAMESERVER_LOCAL,
                    ],
                },
            },
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                        InterfaceIPv4.AUTO_DNS: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.AUTO_DNS: False,
                    },
                }
            ],
        }
    )
    assert _poll(_has_ipv4_dhcp_gateway)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_dhcpv4_addr)
    assert _poll(_has_dhcpv6_addr)
    new_state = libnmstate.show()
    # K8S and NM CI has an extra interface configured as auto_dns: true,
    # which will append extra DNS entries to what we desired
    assert new_state[DNS.KEY][DNS.CONFIG][DNS.SERVER][:2] == [
        IPV6_DNS_NAMESERVER,
        IPV6_DNS_NAMESERVER_LOCAL,
    ]
    assert new_state[DNS.KEY][DNS.RUNNING][DNS.SERVER][:2] == [
        IPV6_DNS_NAMESERVER,
        IPV6_DNS_NAMESERVER_LOCAL,
    ]
    # Remove DNS server before clean up
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


def _has_ipv6_token_addr(token):
    current_state = statelib.show_only((DHCP_CLI_NIC,))[Interface.KEY][0]
    found = False
    addrs = current_state[Interface.IPV6].get(InterfaceIPv6.ADDRESS, [])
    logging.debug("Current IPv6 address of {}: {}".format(DHCP_CLI_NIC, addrs))
    for addr in addrs:
        if addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH] == 64 and addr[
            InterfaceIPv6.ADDRESS_IP
        ].endswith(token):
            found = True
            break
    return found


@pytest.fixture
def dhcpcli_with_ipv6_token(dhcpcli_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.TOKEN: TEST_IPV6_TOKEN,
                    },
                }
            ],
        }
    )
    yield


def test_set_ipv6_token(dhcpcli_with_ipv6_token):
    assert _poll(_has_dhcpv6_addr)
    assert _has_ipv6_token_addr(TEST_IPV6_TOKEN)


def test_remove_ipv6_token_with_empty_str(dhcpcli_with_ipv6_token):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.TOKEN: "",
                    },
                }
            ],
        }
    )
    assert _poll(_has_dhcpv6_addr)
    assert not _has_ipv6_token_addr(TEST_IPV6_TOKEN)


def test_remove_ipv6_token_with_all_zero(dhcpcli_with_ipv6_token):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.TOKEN: "::",
                    },
                }
            ],
        }
    )
    assert _poll(_has_dhcpv6_addr)
    assert not _has_ipv6_token_addr(TEST_IPV6_TOKEN)


def test_set_ipv6_token_with_none_compact_format(dhcpcli_with_ipv6_token):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.TOKEN: TEST_IPV6_TOKEN_IPV4_COMPAT,
                    },
                }
            ],
        }
    )
    assert _poll(_has_dhcpv6_addr)
    assert _has_ipv6_token_addr(TEST_IPV6_TOKEN)


def test_change_ipv6_token(dhcpcli_with_ipv6_token):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                        InterfaceIPv6.TOKEN: TEST_IPV6_TOKEN2,
                    },
                }
            ],
        }
    )
    assert _poll(_has_dhcpv6_addr)
    assert _has_ipv6_token_addr(TEST_IPV6_TOKEN2)


def test_ipv6_token_ignored_when_autoconf_off(dhcpcli_with_ipv6_token):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DHCP_CLI_NIC,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: False,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: False,
                        InterfaceIPv6.AUTOCONF: False,
                    },
                }
            ],
        }
    )


def test_desired_ipv6_token_with_autoconf_off(dhcpcli_with_ipv6_token):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DHCP_CLI_NIC,
                        Interface.IPV4: {
                            InterfaceIPv4.ENABLED: False,
                        },
                        Interface.IPV6: {
                            InterfaceIPv6.ENABLED: True,
                            InterfaceIPv6.DHCP: False,
                            InterfaceIPv6.AUTOCONF: False,
                            InterfaceIPv6.TOKEN: TEST_IPV6_TOKEN,
                        },
                    }
                ],
            }
        )


@pytest.mark.tier1
def test_auto_iface_with_static_routes(dhcp_env):
    static_routes = [
        {
            Route.DESTINATION: IPV4_NETWORK1,
            Route.NEXT_HOP_ADDRESS: DHCP_SRV_IP4,
            Route.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
        },
        {
            Route.DESTINATION: IPV6_NETWORK1,
            Route.NEXT_HOP_ADDRESS: DHCP_SRV_IP6,
            Route.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
        },
    ]
    desired_state = {
        Route.KEY: {
            Route.CONFIG: static_routes,
        },
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: _create_ipv4_state(enabled=True, dhcp=True),
                Interface.IPV6: _create_ipv6_state(
                    enabled=True, dhcp=True, autoconf=True
                ),
            }
        ],
    }
    libnmstate.apply(desired_state)
    current_config_routes = [
        route
        for route in libnmstate.show()[Route.KEY][Route.CONFIG]
        if route[Route.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
        and route[Route.DESTINATION] in (IPV4_NETWORK1, IPV6_NETWORK1)
    ]
    current_config_routes.sort(key=itemgetter(Route.DESTINATION))

    assert len(current_config_routes) == 2
    assert current_config_routes[0][Route.DESTINATION] == IPV6_NETWORK1
    assert current_config_routes[0][Route.NEXT_HOP_ADDRESS] == DHCP_SRV_IP6
    assert current_config_routes[1][Route.DESTINATION] == IPV4_NETWORK1
    assert current_config_routes[1][Route.NEXT_HOP_ADDRESS] == DHCP_SRV_IP4


def test_switch_auto_to_static_with_dynamic_ips(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = _create_ipv4_state(
        enabled=True, dhcp=True
    )
    dhcp_cli_desired_state[Interface.IPV6] = _create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert _poll(_has_dhcpv4_addr)
    assert _poll(_has_dhcpv6_addr)

    # User might just copy current state and disable DHCP/autoconf
    current_state = statelib.show_only((DHCP_CLI_NIC,))
    new_desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.IPV4: current_state[Interface.KEY][0][
                    Interface.IPV4
                ],
                Interface.IPV6: current_state[Interface.KEY][0][
                    Interface.IPV6
                ],
            }
        ]
    }

    new_desired_state[Interface.KEY][0][Interface.IPV4][
        InterfaceIPv4.DHCP
    ] = False
    new_desired_state[Interface.KEY][0][Interface.IPV6][
        InterfaceIPv6.AUTOCONF
    ] = False
    new_desired_state[Interface.KEY][0][Interface.IPV6][
        InterfaceIPv6.DHCP
    ] = False

    libnmstate.apply(new_desired_state)
    assert not _poll_till_not(_has_ipv4_dhcp_nameserver)
    assert not _poll_till_not(_has_ipv6_auto_gateway)
    assert _poll(_has_dhcpv4_addr)
    assert _poll(_has_dhcpv6_addr)


def test_set_dhcp_fqdn_and_remove(dhcpcli_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.DHCP_SEND_HOSTNAME: True,
                    InterfaceIPv4.DHCP_CUSTOM_HOSTNAME: "dhcpcli.example.net",
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.DHCP: True,
                    InterfaceIPv6.AUTOCONF: True,
                    InterfaceIPv6.DHCP_SEND_HOSTNAME: True,
                    InterfaceIPv6.DHCP_CUSTOM_HOSTNAME: "dhcpcli.example.org",
                },
            }
        ],
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.DHCP_SEND_HOSTNAME: True,
                    InterfaceIPv4.DHCP_CUSTOM_HOSTNAME: "",
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.DHCP: True,
                    InterfaceIPv6.AUTOCONF: True,
                    InterfaceIPv6.DHCP_SEND_HOSTNAME: True,
                    InterfaceIPv6.DHCP_CUSTOM_HOSTNAME: "",
                },
            }
        ],
    }
    libnmstate.apply(desired_state)
    desired_state[Interface.KEY][0][Interface.IPV4].pop(
        InterfaceIPv4.DHCP_CUSTOM_HOSTNAME
    )
    desired_state[Interface.KEY][0][Interface.IPV6].pop(
        InterfaceIPv6.DHCP_CUSTOM_HOSTNAME
    )
    assertlib.assert_state_match(desired_state)


def test_dhcp_hostname_with_send_host_off(dhcpcli_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.DHCP_SEND_HOSTNAME: False,
                    InterfaceIPv4.DHCP_CUSTOM_HOSTNAME: "dhcpcli.example.net",
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.DHCP: True,
                    InterfaceIPv6.AUTOCONF: True,
                    InterfaceIPv6.DHCP_SEND_HOSTNAME: False,
                    InterfaceIPv6.DHCP_CUSTOM_HOSTNAME: "dhcpcli.example.org",
                },
            }
        ],
    }
    libnmstate.apply(desired_state)
    desired_state[Interface.KEY][0][Interface.IPV4].pop(
        InterfaceIPv4.DHCP_CUSTOM_HOSTNAME
    )
    desired_state[Interface.KEY][0][Interface.IPV6].pop(
        InterfaceIPv6.DHCP_CUSTOM_HOSTNAME
    )
    assertlib.assert_state_match(desired_state)


def test_set_dhcp_host_name_and_remove(dhcpcli_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: DHCP_CLI_NIC,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.DHCP_SEND_HOSTNAME: True,
                    InterfaceIPv4.DHCP_CUSTOM_HOSTNAME: "dhcpcli",
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.DHCP: True,
                    InterfaceIPv6.AUTOCONF: True,
                    InterfaceIPv6.DHCP_SEND_HOSTNAME: True,
                    InterfaceIPv6.DHCP_CUSTOM_HOSTNAME: "dhcpcli6",
                },
            }
        ],
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
def test_auto_ip_with_pre_exist_address_without_dhcp_srv(eth1_up):
    ipv4_state = _create_ipv4_state(enabled=True, dhcp=True)
    ipv4_state[InterfaceIPv4.ADDRESS] = [
        create_ipv4_address_state(
            IPV4_ADDRESS4, 24, valid_left="30sec", preferred_left="30sec"
        ),
    ]
    ipv6_state = _create_ipv6_state(enabled=True, dhcp=True, autoconf=True)
    ipv6_state[InterfaceIPv6.ADDRESS] = [
        create_ipv6_address_state(
            IPV6_ADDRESS4, 64, valid_left="30sec", preferred_left="30sec"
        ),
    ]

    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: ipv4_state,
                Interface.IPV6: ipv6_state,
            }
        ]
    }

    libnmstate.apply(desired_state)
