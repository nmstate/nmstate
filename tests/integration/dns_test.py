# SPDX-License-Identifier: LGPL-2.1-or-later

import json

import pytest
import yaml

import libnmstate
from libnmstate.error import NmstateNotImplementedError
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route

from .testlib import assertlib
from .testlib import cmdlib
from .testlib.bondlib import bond_interface
from .testlib.genconf import gen_conf_apply

IPV4_DNS_NAMESERVERS = ["8.8.8.8", "1.1.1.1"]
EXTRA_IPV4_DNS_NAMESERVER = "9.9.9.9"
IPV6_DNS_NAMESERVERS = ["2001:4860:4860::8888", "2606:4700:4700::1111"]
IPV6_DNS_LONG_NAMESERVER = ["2000:0000:0000:0000:0000:0000:0000:0100"]
EXTRA_IPV6_DNS_NAMESERVER = "2620:fe::9"
EXAMPLE_SEARCHES = ["example.org", "example.com"]
EXAMPLE_SEARCHES2 = ["example.info", "example.org"]
TEST_BOND0 = "test-bond0"

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


@pytest.mark.tier1
@pytest.mark.parametrize(
    "dns_servers",
    [
        (IPV4_DNS_NAMESERVERS + [EXTRA_IPV4_DNS_NAMESERVER]),
        (IPV6_DNS_NAMESERVERS + [EXTRA_IPV6_DNS_NAMESERVER]),
        (IPV4_DNS_NAMESERVERS + [EXTRA_IPV6_DNS_NAMESERVER]),
        (IPV6_DNS_NAMESERVERS + [EXTRA_IPV4_DNS_NAMESERVER]),
        pytest.param(
            (
                [
                    IPV4_DNS_NAMESERVERS[0],
                    EXTRA_IPV6_DNS_NAMESERVER,
                    IPV4_DNS_NAMESERVERS[1],
                ]
            ),
            marks=pytest.mark.xfail(
                reason="Not supported",
                raises=NmstateNotImplementedError,
                strict=True,
            ),
        ),
        pytest.param(
            (
                [
                    IPV6_DNS_NAMESERVERS[0],
                    EXTRA_IPV4_DNS_NAMESERVER,
                    IPV6_DNS_NAMESERVERS[1],
                ]
            ),
            marks=pytest.mark.xfail(
                reason="Not supported",
                raises=NmstateNotImplementedError,
                strict=True,
            ),
        ),
        (IPV4_DNS_NAMESERVERS + IPV6_DNS_NAMESERVERS),
        (IPV6_DNS_NAMESERVERS + IPV4_DNS_NAMESERVERS),
    ],
    ids=[
        "3ipv4",
        "3ipv6",
        "2ipv4+ipv6",
        "2ipv6+ipv4",
        "ipv4+ipv6+ipv4",
        "ipv6+ipv4+ipv6",
        "2ipv4+2ipv6",
        "2ipv6+2ipv4",
    ],
)
def test_dns_edit_3_more_nameservers(dns_servers):
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
    [{DNS.SERVER: [], DNS.SEARCH: []}, {}],
    ids=[
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
    assert {} == current_state[DNS.KEY][DNS.CONFIG]


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


def test_add_non_canonicalized_ipv6_nameserver():
    dns_config = {
        DNS.SERVER: IPV6_DNS_LONG_NAMESERVER,
        DNS.SEARCH: [],
    }
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {
            DNS.CONFIG: dns_config,
        },
    }
    libnmstate.apply(desired_state)

    current_state = libnmstate.show()
    assert "2000::100" in current_state[DNS.KEY][DNS.CONFIG][DNS.SERVER]


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


@pytest.fixture
def static_dns(eth1_up):
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: [IPV6_DNS_NAMESERVERS[0], IPV4_DNS_NAMESERVERS[0]],
                DNS.SEARCH: EXAMPLE_SEARCHES,
            }
        },
    }
    libnmstate.apply(desired_state)
    yield desired_state
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


@pytest.mark.tier1
def test_change_dns_search_only(static_dns):
    desired_state = {
        DNS.KEY: {DNS.CONFIG: {DNS.SEARCH: EXAMPLE_SEARCHES2}},
    }
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert current_state[DNS.KEY][DNS.CONFIG] == {
        DNS.SERVER: [IPV6_DNS_NAMESERVERS[0], IPV4_DNS_NAMESERVERS[0]],
        DNS.SEARCH: EXAMPLE_SEARCHES2,
    }


def test_change_dns_server_only(static_dns):
    desired_state = {
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: [IPV6_DNS_NAMESERVERS[1], IPV4_DNS_NAMESERVERS[1]]
            }
        },
    }
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert current_state[DNS.KEY][DNS.CONFIG] == {
        DNS.SERVER: [IPV6_DNS_NAMESERVERS[1], IPV4_DNS_NAMESERVERS[1]],
        DNS.SEARCH: EXAMPLE_SEARCHES,
    }


def test_nmstatectl_show_dns(static_dns):
    rc, out, err = cmdlib.exec_cmd("nmstatectl show --json".split())
    assert rc == 0
    current_state = json.loads(out)
    assert (
        current_state[DNS.KEY][DNS.CONFIG] == static_dns[DNS.KEY][DNS.CONFIG]
    )


@pytest.mark.tier1
@parametrize_ip_ver
def test_dns_edit_nameserver_with_static_gateway_genconf(dns_config):
    desired_state = {
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {Route.CONFIG: _gen_default_gateway_route()},
        DNS.KEY: {DNS.CONFIG: dns_config},
    }
    with gen_conf_apply(desired_state):
        current_state = libnmstate.show()
        assert dns_config == current_state[DNS.KEY][DNS.CONFIG]


def test_move_dns_from_port_to_controller(static_dns, eth2_up):
    with bond_interface(
        name=TEST_BOND0, port=["eth1", "eth2"], create=False
    ) as state:
        state[Route.KEY] = static_dns[Route.KEY]
        for route in state[Route.KEY][Route.CONFIG]:
            route[Route.NEXT_HOP_INTERFACE] = TEST_BOND0

        state[DNS.KEY] = static_dns[DNS.KEY]
        state[Interface.KEY][0][Interface.IPV4] = static_dns[Interface.KEY][0][
            Interface.IPV4
        ]
        state[Interface.KEY][0][Interface.IPV6] = static_dns[Interface.KEY][0][
            Interface.IPV6
        ]
        libnmstate.apply(state)
        current_state = libnmstate.show()

        assertlib.assert_state_match(state)
        assert state[DNS.KEY][DNS.CONFIG] == current_state[DNS.KEY][DNS.CONFIG]
        # Remove DNS before deleting bond
        libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


def test_changed_dns_from_port_to_controller(static_dns, eth2_up):
    with bond_interface(
        name=TEST_BOND0, port=["eth1", "eth2"], create=False
    ) as state:
        state[Route.KEY] = static_dns[Route.KEY]
        for route in state[Route.KEY][Route.CONFIG]:
            route[Route.NEXT_HOP_INTERFACE] = TEST_BOND0

        state[DNS.KEY] = static_dns[DNS.KEY]
        state[DNS.KEY][DNS.CONFIG][DNS.SEARCH].reverse()
        state[DNS.KEY][DNS.CONFIG][DNS.SERVER].reverse()
        state[Interface.KEY][0][Interface.IPV4] = static_dns[Interface.KEY][0][
            Interface.IPV4
        ]
        state[Interface.KEY][0][Interface.IPV6] = static_dns[Interface.KEY][0][
            Interface.IPV6
        ]
        libnmstate.apply(state)
        current_state = libnmstate.show()

        assertlib.assert_state_match(state)
        assert state[DNS.KEY][DNS.CONFIG] == current_state[DNS.KEY][DNS.CONFIG]
        # Remove DNS before deleting bond
        libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


def test_uncompare_dns_servers(static_dns):
    desired_state = yaml.load(
        """---
        dns-resolver:
          config:
            server:
            - 2001:Db8:0:0:0:0:0:1
            - ::fFfF:192.0.2.1
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    current_state = libnmstate.show()
    assert "2001:db8::1" in current_state[DNS.KEY][DNS.CONFIG][DNS.SERVER]
    assert "::ffff:192.0.2.1" in current_state[DNS.KEY][DNS.CONFIG][DNS.SERVER]
