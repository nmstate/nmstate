#
# Copyright (c) 2019 Red Hat, Inc.
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

import libnmstate.nm.connection as nm_connection
import libnmstate.nm.dns as nm_dns
import libnmstate.nm.ipv4 as nm_ipv4
import libnmstate.nm.ipv6 as nm_ipv6
from libnmstate.state import State
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route


TEST_IPV4_GATEWAY_IFACE = "eth1"
TEST_IPV6_GATEWAY_IFACE = "eth2"
TEST_STATIC_ROUTE_IFACE = "eth3"

TEST_IFACE1 = "eth4"


def _get_test_dns_v4():
    return {
        nm_dns.DNS_METADATA_PRIORITY: 40,
        DNS.SERVER: ["8.8.8.8", "1.1.1.1"],
        DNS.SEARCH: ["example.org", "example.com"],
    }


def _get_test_dns_v6():
    return {
        nm_dns.DNS_METADATA_PRIORITY: 40,
        DNS.SERVER: ["2001:4860:4860::8888", "2606:4700:4700::1111"],
        DNS.SEARCH: ["example.net", "example.edu"],
    }


parametrize_ip_ver = pytest.mark.parametrize(
    "nm_ip", [(nm_ipv4), (nm_ipv6)], ids=["ipv4", "ipv6"]
)


parametrize_ip_ver_dns = pytest.mark.parametrize(
    "nm_ip, get_test_dns_func",
    [(nm_ipv4, _get_test_dns_v4), (nm_ipv6, _get_test_dns_v6)],
    ids=["ipv4", "ipv6"],
)


@parametrize_ip_ver
def test_add_dns_empty(nm_ip):
    dns_conf = {}
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, nm_dns.DNS_METADATA: dns_conf},
        base_con_profile=None,
    )

    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_add_dns(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, nm_dns.DNS_METADATA: dns_conf},
        base_con_profile=None,
    )

    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_add_dns_duplicate_server(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    dns_conf[DNS.SERVER] = [dns_conf[DNS.SERVER][0], dns_conf[DNS.SERVER][0]]
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, nm_dns.DNS_METADATA: dns_conf},
        base_con_profile=None,
    )

    dns_conf[DNS.SERVER] = [dns_conf[DNS.SERVER][0]]
    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_add_dns_duplicate_search(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    dns_conf[DNS.SEARCH] = [dns_conf[DNS.SEARCH][0], dns_conf[DNS.SEARCH][0]]
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, nm_dns.DNS_METADATA: dns_conf},
        base_con_profile=None,
    )

    dns_conf[DNS.SEARCH] = [dns_conf[DNS.SEARCH][0]]
    _assert_dns(setting_ip, dns_conf)


@parametrize_ip_ver_dns
def test_clear_dns(nm_ip, get_test_dns_func):
    dns_conf = get_test_dns_func()
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, nm_dns.DNS_METADATA: dns_conf},
        base_con_profile=None,
    )
    con_profile = nm_connection.ConnectionProfile()
    con_profile.create([setting_ip])
    new_setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, nm_dns.DNS_METADATA: {}},
        base_con_profile=con_profile.profile,
    )

    _assert_dns(new_setting_ip, {})


def _assert_dns(setting_ip, dns_conf):
    assert setting_ip.props.dns == dns_conf.get(DNS.SERVER, [])
    assert setting_ip.props.dns_search == dns_conf.get(DNS.SEARCH, [])
    priority = dns_conf.get(
        nm_dns.DNS_METADATA_PRIORITY, nm_dns.DEFAULT_DNS_PRIORITY
    )
    assert setting_ip.props.dns_priority == priority


parametrize_ip_ver = pytest.mark.parametrize(
    "families",
    [(Interface.IPV4,), (Interface.IPV6,), (Interface.IPV4, InterfaceIPv6)],
    ids=["ipv4", "ipv6", "ipv4&ipv6"],
)


@parametrize_ip_ver
def test_find_interfaces_for_dns_with_static_gateways(families):
    state = _get_test_desired_state_static_gateway(families)
    expected_ifaces = [None, None]
    if Interface.IPV4 in families:
        expected_ifaces[0] = TEST_IPV4_GATEWAY_IFACE
    if Interface.IPV6 in families:
        expected_ifaces[1] = TEST_IPV6_GATEWAY_IFACE
    expected_ifaces = tuple(expected_ifaces)
    assert expected_ifaces == nm_dns.find_interfaces_for_name_servers(
        State(state)
    )


def test_find_interfaces_for_dns_with_no_routes():
    state = State(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_IPV4_GATEWAY_IFACE,
                    Interface.STATE: InterfaceState.UP,
                },
                {
                    Interface.NAME: TEST_IPV6_GATEWAY_IFACE,
                    Interface.STATE: InterfaceState.UP,
                },
            ],
        }
    )
    assert (None, None) == nm_dns.find_interfaces_for_name_servers(state)


def test_find_interfaces_for_dns_with_no_gateway():
    state = State(_get_test_desired_state_static_gateway(()))
    assert (None, None) == nm_dns.find_interfaces_for_name_servers(state)


@parametrize_ip_ver
def test_find_interfaces_for_dns_with_dynamic_ip_but_no_auto_dns(families):
    state = State(_get_test_desired_state_dynamic_ip_but_no_auto_dns(families))
    expected_ifaces = [None, None]
    if Interface.IPV4 in families:
        expected_ifaces[0] = TEST_IFACE1
    if Interface.IPV6 in families:
        expected_ifaces[1] = TEST_IFACE1
    expected_ifaces = tuple(expected_ifaces)
    assert expected_ifaces == nm_dns.find_interfaces_for_name_servers(state)


@parametrize_ip_ver
def test_find_interfaces_for_dns_with_dynamic_ip_and_auto_dns(families):
    iface_state = {
        Interface.NAME: TEST_IFACE1,
        Interface.STATE: InterfaceState.UP,
        Interface.IPV4: {InterfaceIPv4.ENABLED: False},
        Interface.IPV6: {InterfaceIPv6.ENABLED: False},
    }
    if Interface.IPV4 in families:
        iface_state[Interface.IPV4][InterfaceIPv4.ENABLED] = True
        iface_state[Interface.IPV4][InterfaceIPv4.DHCP] = True
        iface_state[Interface.IPV4][InterfaceIPv4.AUTO_DNS] = True

    if Interface.IPV6 in families:
        iface_state[Interface.IPV6][InterfaceIPv6.ENABLED] = True
        iface_state[Interface.IPV6][InterfaceIPv6.DHCP] = True
        iface_state[Interface.IPV6][InterfaceIPv6.AUTOCONF] = True
        iface_state[Interface.IPV6][InterfaceIPv6.AUTO_DNS] = True
    state = State({Interface.KEY: [iface_state]})
    assert (None, None) == nm_dns.find_interfaces_for_name_servers(state)


@parametrize_ip_ver
def test_find_interfaces_for_dns_prefer_static_gateway(families):
    state = _get_test_desired_state_static_gateway(families)
    state2 = _get_test_desired_state_dynamic_ip_but_no_auto_dns(families)
    state[Interface.KEY].extend(state2[Interface.KEY])
    state = State(state)

    expected_ifaces = [None, None]
    if Interface.IPV4 in families:
        expected_ifaces[0] = TEST_IPV4_GATEWAY_IFACE
    if Interface.IPV6 in families:
        expected_ifaces[1] = TEST_IPV6_GATEWAY_IFACE
    expected_ifaces = tuple(expected_ifaces)
    assert expected_ifaces == nm_dns.find_interfaces_for_name_servers(state)


def _get_test_ipv4_gateway():
    return {
        Route.DESTINATION: "0.0.0.0/0",
        Route.METRIC: 200,
        Route.NEXT_HOP_ADDRESS: "192.0.2.1",
        Route.NEXT_HOP_INTERFACE: TEST_IPV4_GATEWAY_IFACE,
        Route.TABLE_ID: 54,
    }


def _get_test_ipv6_gateway():
    return {
        Route.DESTINATION: "::/0",
        Route.METRIC: 201,
        Route.NEXT_HOP_ADDRESS: "2001:db8:2::f",
        Route.NEXT_HOP_INTERFACE: TEST_IPV6_GATEWAY_IFACE,
        Route.TABLE_ID: 54,
    }


def _get_test_static_routes():
    return [
        {
            Route.DESTINATION: "2001:db8:3::1",
            Route.METRIC: 201,
            Route.NEXT_HOP_ADDRESS: "2001:db8:2::f",
            Route.NEXT_HOP_INTERFACE: TEST_STATIC_ROUTE_IFACE,
            Route.TABLE_ID: 54,
        },
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.METRIC: 201,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: TEST_STATIC_ROUTE_IFACE,
            Route.TABLE_ID: 54,
        },
    ]


def _get_test_desired_state_static_gateway(families):
    state = {
        Route.KEY: {Route.CONFIG: _get_test_static_routes()},
        Interface.KEY: [
            {
                Interface.NAME: TEST_IPV4_GATEWAY_IFACE,
                Interface.STATE: InterfaceState.UP,
            },
            {
                Interface.NAME: TEST_IPV6_GATEWAY_IFACE,
                Interface.STATE: InterfaceState.UP,
            },
            {
                Interface.NAME: TEST_STATIC_ROUTE_IFACE,
                Interface.STATE: InterfaceState.UP,
            },
        ],
    }
    if Interface.IPV4 in families:
        state[Route.KEY][Route.CONFIG].append(_get_test_ipv4_gateway())
    if Interface.IPV6 in families:
        state[Route.KEY][Route.CONFIG].append(_get_test_ipv6_gateway())
    return state


def _get_test_desired_state_dynamic_ip_but_no_auto_dns(families):
    iface_state = {
        Interface.NAME: TEST_IFACE1,
        Interface.STATE: InterfaceState.UP,
        Interface.IPV4: {InterfaceIPv4.ENABLED: False},
        Interface.IPV6: {InterfaceIPv6.ENABLED: False},
    }
    if Interface.IPV4 in families:
        iface_state[Interface.IPV4][InterfaceIPv4.ENABLED] = True
        iface_state[Interface.IPV4][InterfaceIPv4.DHCP] = True
        iface_state[Interface.IPV4][InterfaceIPv4.AUTO_DNS] = False

    if Interface.IPV6 in families:
        iface_state[Interface.IPV6][InterfaceIPv6.ENABLED] = True
        iface_state[Interface.IPV6][InterfaceIPv6.DHCP] = True
        iface_state[Interface.IPV6][InterfaceIPv6.AUTOCONF] = True
        iface_state[Interface.IPV6][InterfaceIPv6.AUTO_DNS] = False

    return {Interface.KEY: [iface_state]}
