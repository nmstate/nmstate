#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
from copy import deepcopy
import logging
import os
import time

import pytest

import libnmstate
from libnmstate.schema import Constants
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route as RT

from libnmstate.error import NmstateNotImplementedError

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import bondlib
from .testlib import ifacelib
from .testlib import statelib
from .testlib.ifacelib import get_mac_address
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import create_bridge_subtree_state
from .testlib.bridgelib import linux_bridge
from .testlib.retry import retry_till_true_or_timeout

ETH1 = "eth1"

DEFAULT_TIMEOUT = 20
NM_DHCP_TIMEOUT_DEFAULT = 45
# The default IPv6 RA/Autoconf timeout is 30 seconds, less than above.
NM_IPV6_AUTOCONF_TIMEOUT_DEFAULT = 30

IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:2::1"
IPV6_ADDRESS3 = "2001:db8:1::3"
IPV4_NETWORK1 = "203.0.113.0/24"
IPV6_NETWORK1 = "2001:db8:2::/64"
IPV4_CLASSLESS_ROUTE_DST_NET1 = "198.51.100.0/24"
IPV4_CLASSLESS_ROUTE_NEXT_HOP1 = "192.0.2.1"
IPV6_CLASSLESS_ROUTE_PREFIX = "2001:db8:f"
IPV6_CLASSLESS_ROUTE_DST_NET1 = "{}::/64".format(IPV6_CLASSLESS_ROUTE_PREFIX)

TEST_BRIDGE_NIC = "brtest0"

DHCP_SRV_NIC = "dhcpsrv"
DHCP_CLI_NIC = "dhcpcli"
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

SYSFS_DISABLE_IPV6_FILE = "/proc/sys/net/ipv6/conf/{}/disable_ipv6".format(
    DHCP_SRV_NIC
)
SYSFS_DISABLE_RA_SRV = "/proc/sys/net/ipv6/conf/{}/accept_ra".format(
    DHCP_SRV_NIC
)

parametrize_ip_ver = pytest.mark.parametrize(
    "ip_ver",
    [(Interface.IPV4,), (Interface.IPV6,), (Interface.IPV4, Interface.IPV6)],
    ids=["ipv4", "ipv6", "ipv4&6"],
)


@pytest.fixture(scope="module")
def dhcp_env():
    try:
        _create_veth_pair()
        _setup_dhcp_nics()

        with open(DNSMASQ_CONF_PATH, "w") as fd:
            fd.write(DNSMASQ_CONF_STR)
        assert cmdlib.exec_cmd(["systemctl", "restart", "dnsmasq"])[0] == 0

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
                Interface.IPV4: create_ipv4_state(enabled=True, dhcp=True),
                Interface.IPV6: create_ipv6_state(
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
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
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
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv6_auto_gateway)
    assert _poll(_has_ipv6_auto_extra_route)
    assert _poll(_has_ipv6_auto_nameserver)


def test_dhcp_with_addresses(dhcpcli_up):
    ipv4_state = create_ipv4_state(enabled=True, dhcp=True)
    ipv4_state[InterfaceIPv4.ADDRESS] = [
        create_ipv4_address_state(IPV4_ADDRESS1, 24),
        create_ipv4_address_state(IPV4_ADDRESS2, 24),
    ]
    ipv6_state = create_ipv6_state(enabled=True, dhcp=True, autoconf=True)
    ipv6_state[InterfaceIPv6.ADDRESS] = [
        create_ipv6_address_state(IPV6_ADDRESS1, 64),
        create_ipv6_address_state(IPV6_ADDRESS2, 64),
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

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_ipv4_dhcp_on_bond(dhcpcli_up):
    ipv4_state = {Interface.IPV4: create_ipv4_state(enabled=True, dhcp=True)}
    with bondlib.bond_interface(
        "bond99", slaves=[DHCP_CLI_NIC], extra_iface_state=ipv4_state
    ) as desired_state:
        assertlib.assert_state(desired_state)


def test_ipv4_dhcp_ignore_gateway(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
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
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
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
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
        enabled=True, dhcp=True, auto_routes=False
    )

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert _poll(_has_ipv4_dhcp_nameserver)
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_and_autoconf_ignore_gateway(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
    ipv4_state = create_ipv4_state(
        enabled=True,
        dhcp=False,
        auto_dns=False,
        auto_gateway=False,
        auto_routes=False,
    )
    ipv4_state.pop(InterfaceIPv4.ENABLED)
    dhcp_cli_desired_state[Interface.IPV4] = ipv4_state

    libnmstate.apply(desired_state)

    current_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_current_state = current_state[Interface.KEY][0]
    ipv4_current_state = dhcp_cli_current_state[Interface.IPV4]
    assert not ipv4_current_state[InterfaceIPv4.DHCP]
    assert InterfaceIPv4.AUTO_ROUTES not in ipv4_current_state
    assert InterfaceIPv4.AUTO_DNS not in ipv4_current_state
    assert InterfaceIPv4.AUTO_GATEWAY not in ipv4_current_state
    assert not _poll(_has_ipv4_dhcp_nameserver)
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
    ipv6_state = create_ipv6_state(
        enabled=True,
        dhcp=False,
        autoconf=False,
        auto_dns=False,
        auto_gateway=False,
        auto_routes=False,
    )
    ipv6_state.pop(InterfaceIPv6.ENABLED)
    dhcp_cli_desired_state[Interface.IPV6] = ipv6_state

    libnmstate.apply(desired_state)

    current_state = statelib.show_only((DHCP_CLI_NIC,))
    dhcp_cli_current_state = current_state[Interface.KEY][0]
    ipv6_current_state = dhcp_cli_current_state[Interface.IPV6]
    assert not ipv6_current_state[InterfaceIPv6.DHCP]
    assert InterfaceIPv6.AUTO_ROUTES not in ipv6_current_state
    assert InterfaceIPv6.AUTO_DNS not in ipv6_current_state
    assert InterfaceIPv6.AUTO_GATEWAY not in ipv6_current_state
    assert not _poll(_has_ipv6_auto_gateway)
    assert not _has_ipv6_auto_extra_route()
    assert not _has_ipv6_auto_nameserver()


def test_ipv4_dhcp_switch_on_to_off(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
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
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(enabled=True)

    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
    assert not _poll(_has_ipv4_dhcp_nameserver)
    assert not _has_ipv4_dhcp_gateway()
    assert not _has_ipv4_classless_route()


def test_ipv6_dhcp_switch_on_to_off(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(enabled=True)

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
    assert not _poll(_has_ipv6_auto_gateway)
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
        Interface.IPV4: create_ipv4_state(enabled=True, dhcp=True),
        Interface.IPV6: create_ipv6_state(
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
    assert origin_ipv4_state == new_ipv4_state
    assert origin_ipv6_state == new_ipv6_state


@pytest.mark.tier1
def test_slave_ipaddr_learned_via_dhcp_added_as_static_to_linux_bridge(
    dhcpcli_up,
):
    dhcpcli_up[Interface.KEY][0][Interface.IPV4] = create_ipv4_state(
        enabled=True, dhcp=True
    )

    libnmstate.apply(dhcpcli_up)

    assert _poll(_has_dhcpv4_addr)

    slave_ifname = dhcpcli_up[Interface.KEY][0][Interface.NAME]
    slave_state = statelib.show_only((slave_ifname,))
    slave_iface_state = slave_state[Interface.KEY][0]
    dhcpcli_ip = slave_iface_state[Interface.IPV4][InterfaceIPv4.ADDRESS]

    bridge_state = add_port_to_bridge(
        create_bridge_subtree_state(), slave_ifname
    )

    ipv4_state = create_ipv4_state(enabled=True, dhcp=False)
    ipv4_state[InterfaceIPv4.ADDRESS] = dhcpcli_ip
    with linux_bridge(
        TEST_BRIDGE_NIC,
        bridge_state,
        extra_iface_state={Interface.IPV4: ipv4_state},
        create=False,
    ) as state:
        state[Interface.KEY].append(
            {
                Interface.NAME: slave_ifname,
                Interface.IPV4: create_ipv4_state(enabled=False),
                Interface.IPV6: create_ipv6_state(enabled=False),
            }
        )
        libnmstate.apply(state)

        assertlib.assert_state_match(state)


@pytest.mark.xfail(raises=NmstateNotImplementedError)
def test_ipv6_autoconf_only(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
        enabled=True, autoconf=True
    )

    libnmstate.apply(desired_state)


def _create_veth_pair():
    assert (
        cmdlib.exec_cmd(
            [
                "ip",
                "link",
                "add",
                DHCP_SRV_NIC,
                "type",
                "veth",
                "peer",
                "name",
                DHCP_CLI_NIC,
            ]
        )[0]
        == 0
    )


def _remove_veth_pair():
    cmdlib.exec_cmd(["ip", "link", "del", "dev", DHCP_SRV_NIC])


def _setup_dhcp_nics():
    assert cmdlib.exec_cmd(["ip", "link", "set", DHCP_SRV_NIC, "up"])[0] == 0
    assert cmdlib.exec_cmd(["ip", "link", "set", DHCP_CLI_NIC, "up"])[0] == 0
    assert (
        cmdlib.exec_cmd(
            [
                "ip",
                "addr",
                "add",
                "{}/24".format(DHCP_SRV_IP4),
                "dev",
                DHCP_SRV_NIC,
            ]
        )[0]
        == 0
    )
    assert (
        cmdlib.exec_cmd(
            ["nmcli", "device", "set", DHCP_CLI_NIC, "managed", "yes"]
        )[0]
        == 0
    )
    # This stop dhcp server NIC get another IPv6 address from dnsmasq.
    with open(SYSFS_DISABLE_RA_SRV, "w") as fd:
        fd.write("0")

    with open(SYSFS_DISABLE_IPV6_FILE, "w") as fd:
        fd.write("0")

    assert (
        cmdlib.exec_cmd(
            [
                "ip",
                "addr",
                "add",
                "{}/64".format(DHCP_SRV_IP6),
                "dev",
                DHCP_SRV_NIC,
            ]
        )[0]
        == 0
    )

    assert (
        cmdlib.exec_cmd(
            [
                "ip",
                "addr",
                "add",
                "{}/64".format(DHCP_SRV_IP6_2),
                "dev",
                DHCP_SRV_NIC,
            ]
        )[0]
        == 0
    )


def _clean_up():
    cmdlib.exec_cmd(["systemctl", "stop", "dnsmasq"])
    _remove_veth_pair()
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
        libnmstate.show().get(Constants.ROUTES, {}).get(RT.RUNNING, [])
    )
    logging.debug("Current running routes: {}".format(running_routes))
    return running_routes


def _poll(func, *args, **kwargs):
    return retry_till_true_or_timeout(DEFAULT_TIMEOUT, func, *args, **kwargs)


def _has_ipv6_auto_gateway(nic=DHCP_CLI_NIC):
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV6_DEFAULT_GATEWAY
            and route[RT.NEXT_HOP_INTERFACE] == nic
        ):
            return True
    return False


def _has_ipv6_auto_extra_route():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV6_CLASSLESS_ROUTE_DST_NET1
            and route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
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
            route[RT.DESTINATION] == IPV4_DEFAULT_GATEWAY
            and route[RT.NEXT_HOP_INTERFACE] == nic
        ):
            return True
    return False


def _has_ipv4_classless_route():
    routes = _get_running_routes()
    for route in routes:
        if (
            route[RT.DESTINATION] == IPV4_CLASSLESS_ROUTE_DST_NET1
            and route[RT.NEXT_HOP_ADDRESS] == IPV4_CLASSLESS_ROUTE_NEXT_HOP1
            and route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
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


def create_ipv4_state(
    enabled, dhcp=False, auto_dns=True, auto_gateway=True, auto_routes=True
):
    return {
        InterfaceIPv4.ENABLED: enabled,
        InterfaceIPv4.DHCP: dhcp,
        InterfaceIPv4.AUTO_DNS: auto_dns,
        InterfaceIPv4.AUTO_GATEWAY: auto_gateway,
        InterfaceIPv4.AUTO_ROUTES: auto_routes,
    }


def create_ipv6_state(
    enabled,
    dhcp=False,
    autoconf=False,
    auto_dns=True,
    auto_gateway=True,
    auto_routes=True,
):
    return {
        InterfaceIPv6.ENABLED: enabled,
        InterfaceIPv6.DHCP: dhcp,
        InterfaceIPv6.AUTOCONF: autoconf,
        InterfaceIPv6.AUTO_DNS: auto_dns,
        InterfaceIPv6.AUTO_GATEWAY: auto_gateway,
        InterfaceIPv6.AUTO_ROUTES: auto_routes,
    }


def create_ipv4_address_state(address, prefix_length):
    return {
        InterfaceIPv4.ADDRESS_IP: address,
        InterfaceIPv4.ADDRESS_PREFIX_LENGTH: prefix_length,
    }


def create_ipv6_address_state(address, prefix_length):
    return {
        InterfaceIPv6.ADDRESS_IP: address,
        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: prefix_length,
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
        ifstate[Interface.IPV4] = create_ipv4_state(enabled=True, dhcp=True)
    if Interface.IPV6 in ip_ver:
        ifstate[Interface.IPV6] = create_ipv6_state(
            enabled=True, dhcp=True, autoconf=True
        )
    libnmstate.apply({Interface.KEY: [ifstate]})


@pytest.mark.tier1
def test_dummy_disable_ip_stack_with_on_going_dhcp(dummy00):
    ifstate = dummy00
    ifstate[Interface.IPV4] = create_ipv4_state(enabled=True, dhcp=True)
    ifstate[Interface.IPV6] = create_ipv6_state(
        enabled=True, dhcp=True, autoconf=True
    )
    libnmstate.apply({Interface.KEY: [ifstate]})
    ifstate[Interface.IPV4] = create_ipv4_state(enabled=False)
    ifstate[Interface.IPV6] = create_ipv6_state(enabled=False)
    libnmstate.apply({Interface.KEY: [ifstate]})


def test_dhcp4_with_static_ipv6(dhcpcli_up):
    desired_state = dhcpcli_up
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
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
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
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

    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
        ifstate[Interface.IPV4] = create_ipv4_state(enabled=True, dhcp=True)
    if Interface.IPV6 in ip_ver:
        ifstate[Interface.IPV6] = create_ipv6_state(
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
    ifstate[Interface.IPV4] = create_ipv4_state(enabled=False)
    ifstate[Interface.IPV6] = create_ipv6_state(
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
    desired_state[RT.KEY] = {
        RT.CONFIG: [
            {
                RT.DESTINATION: IPV4_DEFAULT_GATEWAY,
                RT.NEXT_HOP_ADDRESS: DHCP_SRV_IP4,
                RT.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
            {
                RT.DESTINATION: IPV4_NETWORK1,
                RT.NEXT_HOP_ADDRESS: DHCP_SRV_IP4,
                RT.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
            {
                RT.DESTINATION: IPV6_DEFAULT_GATEWAY,
                RT.NEXT_HOP_ADDRESS: IPV6_ADDRESS3,
                RT.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
            },
            {
                RT.DESTINATION: IPV6_NETWORK1,
                RT.NEXT_HOP_ADDRESS: IPV6_ADDRESS3,
                RT.NEXT_HOP_INTERFACE: DHCP_CLI_NIC,
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
    desired_state.pop(RT.KEY)
    dhcp_cli_desired_state = desired_state[Interface.KEY][0]
    dhcp_cli_desired_state[Interface.STATE] = InterfaceState.UP
    dhcp_cli_desired_state[Interface.IPV4] = create_ipv4_state(
        enabled=True, dhcp=True
    )
    dhcp_cli_desired_state[Interface.IPV6] = create_ipv6_state(
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
        for route in libnmstate.show()[RT.KEY][RT.CONFIG]
        if route[RT.NEXT_HOP_INTERFACE] == DHCP_CLI_NIC
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
    iface_state[Interface.IPV4] = create_ipv4_state(enabled=False)
    iface_state[Interface.IPV6] = create_ipv6_state(
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
        Interface.IPV4: create_ipv4_state(
            enabled=True, dhcp=True, auto_dns=False
        ),
        Interface.IPV6: create_ipv6_state(
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
