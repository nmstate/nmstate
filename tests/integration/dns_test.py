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

import pytest

import libnmstate
from libnmstate.error import NmstateNotImplementedError
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route


IPV4_DNS_NAMESERVERS = ["8.8.8.8", "1.1.1.1"]
EXTRA_IPV4_DNS_NAMESERVER = "9.9.9.9"
IPV6_DNS_NAMESERVERS = ["2001:4860:4860::8888", "2606:4700:4700::1111"]
EXTRA_IPV6_DNS_NAMESERVER = "2620:fe::9"
EXAMPLE_SEARCHES = ["example.org", "example.com"]

parametrize_ip_ver = pytest.mark.parametrize(
    "dns_config",
    [
        ({DNS.SERVER: IPV4_DNS_NAMESERVERS, DNS.SEARCH: EXAMPLE_SEARCHES}),
        ({DNS.SERVER: IPV6_DNS_NAMESERVERS, DNS.SEARCH: EXAMPLE_SEARCHES}),
    ],
    ids=["ipv4", "ipv6"],
)

DUMMY0 = "dummy0"


@pytest.fixture(scope="function", autouse=True)
def dns_test_env(eth1_up, eth2_up):
    yield
    # Remove DNS config as it be saved in eth1 or eth2 which might trigger
    # failure when bring eth1/eth2 down.
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        DNS.KEY: {DNS.CONFIG: {DNS.SERVER: [], DNS.SEARCH: []}},
    }
    libnmstate.apply(desired_state)


@pytest.mark.tier1
@parametrize_ip_ver
def test_dns_edit_nameserver_with_static_gateway(dns_config):
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


def test_dns_edit_ipv4_nameserver_before_ipv6():
    dns_config = {
        DNS.SERVER: [IPV4_DNS_NAMESERVERS[0], IPV6_DNS_NAMESERVERS[0]],
        DNS.SEARCH: [],
    }
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


@pytest.mark.tier1
def test_dns_edit_ipv6_nameserver_before_ipv4():
    dns_config = {
        DNS.SERVER: [IPV6_DNS_NAMESERVERS[0], IPV4_DNS_NAMESERVERS[0]],
        DNS.SEARCH: [],
    }
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


@pytest.mark.parametrize(
    "dns_servers",
    [
        (IPV4_DNS_NAMESERVERS + [EXTRA_IPV4_DNS_NAMESERVER]),
        (IPV6_DNS_NAMESERVERS + [EXTRA_IPV6_DNS_NAMESERVER]),
        pytest.param(
            (IPV4_DNS_NAMESERVERS + [EXTRA_IPV6_DNS_NAMESERVER]),
            marks=pytest.mark.xfail(
                reason="Not supported",
                raises=NmstateNotImplementedError,
                strict=True,
            ),
        ),
        pytest.param(
            (IPV6_DNS_NAMESERVERS + [EXTRA_IPV4_DNS_NAMESERVER]),
            marks=pytest.mark.xfail(
                reason="Not supported",
                raises=NmstateNotImplementedError,
                strict=True,
            ),
        ),
    ],
    ids=["ipv4", "ipv6", "ipv4+ipv6", "ipv6+ipv4"],
)
def test_dns_edit_three_nameservers(dns_servers):
    dns_config = {
        DNS.SERVER: dns_servers,
        DNS.SEARCH: [],
    }
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


@pytest.mark.tier1
@pytest.mark.parametrize(
    "empty_dns_config",
    [{DNS.SERVER: []}, {DNS.SEARCH: []}, {DNS.SERVER: [], DNS.SEARCH: []}, {}],
    ids=[
        "empty_server",
        "empty_search",
        "empty_server_and_search",
        "empty_dict",
    ],
)
def test_remove_dns_config(empty_dns_config):
    dns_config = {
        DNS.SERVER: [IPV6_DNS_NAMESERVERS[0], IPV4_DNS_NAMESERVERS[0]],
        DNS.SEARCH: [],
    }
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    libnmstate.apply(desired_state)

    libnmstate.apply(
        {Interface.KEY: [], DNS.KEY: {DNS.CONFIG: empty_dns_config}}
    )
    current_state = libnmstate.show()
    dns_config = {DNS.SERVER: [], DNS.SEARCH: []}
    assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


@pytest.fixture
def dummy0_up():
    dummy_iface_state = {
        Interface.NAME: DUMMY0,
        Interface.TYPE: InterfaceType.DUMMY,
        Interface.STATE: InterfaceState.UP,
    }
    libnmstate.apply({Interface.KEY: [dummy_iface_state]})
    yield dummy_iface_state
    dummy_iface_state[Interface.STATE] = InterfaceState.ABSENT
    libnmstate.apply({Interface.KEY: [dummy_iface_state]})


def test_preserve_dns_config(dummy0_up):
    dns_config = {
        DNS.SERVER: [IPV6_DNS_NAMESERVERS[0], IPV4_DNS_NAMESERVERS[0]],
        DNS.SEARCH: [],
    }
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    libnmstate.apply(desired_state)

    # Add new dummy interface with default gateway, nmstate should
    # preserve the existing DNS configure as interface holding DNS
    # configuration is not changed and DNS configure is still the same.
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.IPV4: {
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: "192.0.2.250",
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                        InterfaceIPv4.ENABLED: True,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: "2001:db8:f::1",
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                        InterfaceIPv6.ENABLED: True,
                    },
                }
            ],
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.DESTINATION: "0.0.0.0/0",
                        Route.NEXT_HOP_ADDRESS: "192.0.2.2",
                        Route.NEXT_HOP_INTERFACE: DUMMY0,
                    },
                    {
                        Route.DESTINATION: "::/0",
                        Route.NEXT_HOP_ADDRESS: "2001:db8:f::2",
                        Route.NEXT_HOP_INTERFACE: DUMMY0,
                    },
                ]
            },
        }
    )

    current_state = libnmstate.show()

    assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


@pytest.fixture
def setup_ipv4_ipv6_name_server():
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: [IPV6_DNS_NAMESERVERS[0], IPV4_DNS_NAMESERVERS[0]],
                DNS.SEARCH: [],
            }
        },
    }
    libnmstate.apply(desired_state)
    yield desired_state


def test_preserve_dns_config_with_empty_state(setup_ipv4_ipv6_name_server):
    old_state = setup_ipv4_ipv6_name_server

    libnmstate.apply({Interface.KEY: []})
    current_state = libnmstate.show()

    assert old_state[DNS.KEY][DNS.CONFIG] == current_state[DNS.KEY][DNS.CONFIG]


def _get_test_iface_states():
    return [
        {
            Interface.NAME: "eth1",
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                InterfaceIPv4.ADDRESS: [
                    {
                        InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                        InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                    }
                ],
                InterfaceIPv4.DHCP: False,
                InterfaceIPv4.ENABLED: True,
            },
            Interface.IPV6: {
                InterfaceIPv6.ADDRESS: [
                    {
                        InterfaceIPv6.ADDRESS_IP: "2001:db8:1::1",
                        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                    }
                ],
                InterfaceIPv6.DHCP: False,
                InterfaceIPv6.AUTOCONF: False,
                InterfaceIPv6.ENABLED: True,
            },
        },
        {
            Interface.NAME: "eth2",
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                InterfaceIPv4.ADDRESS: [
                    {
                        InterfaceIPv4.ADDRESS_IP: "198.51.100.1",
                        InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                    }
                ],
                InterfaceIPv4.DHCP: False,
                InterfaceIPv4.ENABLED: True,
            },
            Interface.IPV6: {
                InterfaceIPv6.ADDRESS: [
                    {
                        InterfaceIPv6.ADDRESS_IP: "2001:db8:2::1",
                        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                    }
                ],
                InterfaceIPv6.DHCP: False,
                InterfaceIPv6.AUTOCONF: False,
                InterfaceIPv6.ENABLED: True,
            },
        },
    ]


def _gen_default_gateway_route():
    return [
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 200,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: "eth1",
        },
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 201,
            Route.NEXT_HOP_ADDRESS: "2001:db8:2::f",
            Route.NEXT_HOP_INTERFACE: "eth1",
        },
    ]
