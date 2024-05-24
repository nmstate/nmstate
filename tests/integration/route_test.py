# SPDX-License-Identifier: LGPL-2.1-or-later

import copy

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import iprule
from .testlib.bridgelib import linux_bridge
from .testlib.env import nm_minor_version
from .testlib.genconf import gen_conf_apply
from .testlib.route import assert_routes
from .testlib.route import assert_routes_missing
from .testlib.servicelib import disable_service
from .testlib.yaml import load_yaml

IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV4_ADDRESS3 = "192.0.2.253"
IPV4_LINK_LOCAL_ROUTE = "192.0.2.0/24"
IPV4_ROUTE_TABLE_ID1 = 50
IPV4_ROUTE_TABLE_ID2 = 51
IPV4_EMPTY_ADDRESS = "0.0.0.0"
IPV4_DEFAULT_GATEWAY = "0.0.0.0/0"
IPV4_TEST_NET1 = "203.0.113.0/24"

IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:1::2"
IPV6_ADDRESS3 = "2001:db8:1::3"
IPV6_EMPTY_ADDRESS = "::"
IPV6_DEFAULT_GATEWAY = "::/0"
IPV6_ROUTE_TABLE_ID1 = 50
IPV6_ROUTE_TABLE_ID2 = 51
IPV6_TEST_NET1 = "2001:db8:e::/64"

TEST_ROUTE_TABLE_ID = 99

IPV4_DNS_NAMESERVER = "8.8.8.8"
IPV6_DNS_NAMESERVER = "2001:4860:4860::8888"
DNS_SEARCHES = ["example.org", "example.com"]

IPV6_GATEWAY1 = "2001:db8:1::f"
IPV6_GATEWAY2 = "2001:db8:1::e"

BGP_ROUTE_DST_V4 = "203.0.113.0/25"
BGP_ROUTE_DST_V6 = "2001:db8:b6::/64"

ETH1_INTERFACE_STATE = {
    Interface.NAME: "eth1",
    Interface.STATE: InterfaceState.UP,
    Interface.TYPE: InterfaceType.ETHERNET,
    Interface.IPV4: {
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
        InterfaceIPv4.DHCP: False,
        InterfaceIPv4.ENABLED: True,
    },
    Interface.IPV6: {
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        ],
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.AUTOCONF: False,
        InterfaceIPv6.ENABLED: True,
    },
}

TEST_BRIDGE0 = "linux-br0"
BGP_PROTOCOL_ID = "186"


@pytest.fixture(scope="function", autouse=True)
def clean_up_route_rule():
    yield
    libnmstate.apply(
        {
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.STATE: Route.STATE_ABSENT,
                    }
                ]
            },
            RouteRule.KEY: {
                RouteRule.CONFIG: [
                    {
                        RouteRule.STATE: RouteRule.STATE_ABSENT,
                    }
                ]
            },
            DNS.KEY: {DNS.CONFIG: {}},
        },
    )


@pytest.mark.tier1
def test_add_static_routes(static_eth1_with_routes):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


@pytest.mark.tier1
def test_add_static_route_without_next_hop_address(eth1_up):
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_DEFAULT_GATEWAY,
            Route.NEXT_HOP_ADDRESS: IPV4_EMPTY_ADDRESS,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV6_DEFAULT_GATEWAY,
            Route.NEXT_HOP_ADDRESS: IPV6_EMPTY_ADDRESS,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 42,
    reason="Loopback is only support on NM 1.42+, and blackhole type route "
    "is stored in loopback",
)
def test_add_static_route_with_route_type(eth1_up):
    route = [
        {
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_INTERFACE: "lo",
            Route.ROUTETYPE: Route.ROUTETYPE_BLACKHOLE,
        },
        {
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.ROUTETYPE: Route.ROUTETYPE_UNREACHABLE,
        },
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.ROUTETYPE: Route.ROUTETYPE_PROHIBIT,
        },
        {
            Route.DESTINATION: "0.0.0.0/8",
            Route.ROUTETYPE: Route.ROUTETYPE_BLACKHOLE,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: route},
        }
    )
    routes_output4 = _get_routes_from_iproute(4, "main")
    routes_output6 = _get_routes_from_iproute(6, "main")
    assert IPV4_TEST_NET1 in routes_output4
    assert Route.ROUTETYPE_BLACKHOLE in routes_output4
    assert "198.51.100.0/24" in routes_output4
    assert "0.0.0.0/8" in routes_output4
    assert Route.ROUTETYPE_PROHIBIT in routes_output4
    assert IPV6_TEST_NET1 in routes_output6
    assert Route.ROUTETYPE_UNREACHABLE in routes_output6


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 42,
    reason="Loopback is only support on NM 1.42+, and blackhole type route "
    "is stored in loopback",
)
def test_add_static_route_and_apply_route_absent(eth1_up):
    routes = [
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.ROUTETYPE: Route.ROUTETYPE_BLACKHOLE,
        },
        {
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
        },
        {
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::b",
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    absent_route = routes[0]
    absent_route[Route.STATE] = Route.STATE_ABSENT
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: [absent_route]},
        }
    )
    remaining_routes = routes[1:]
    cur_state = libnmstate.show()
    assert_routes(remaining_routes, cur_state)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 42,
    reason="Loopback is only support on NM 1.42+, and blackhole type route "
    "is stored in loopback",
)
def test_add_static_Ipv4_route_with_route_type(eth1_up):
    routes = [
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.NEXT_HOP_INTERFACE: "lo",
            Route.ROUTETYPE: Route.ROUTETYPE_BLACKHOLE,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    current_routes = cur_state[Route.KEY][Route.CONFIG]
    for route in current_routes:
        if route.get(Route.ROUTETYPE, None) == Route.ROUTETYPE_BLACKHOLE:
            assert route.get(Route.NEXT_HOP_INTERFACE, None) is None


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 42,
    reason="Loopback is only support on NM 1.42+, and blackhole type route "
    "is stored in loopback",
)
def test_route_type_with_next_hop_interface(eth1_up):
    route = [
        {
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.ROUTETYPE: Route.ROUTETYPE_BLACKHOLE,
        },
    ]
    state = {
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {Route.CONFIG: route},
    }

    with pytest.raises(NmstateValueError):
        libnmstate.apply(state)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 42,
    reason="Loopback is only support on NM 1.42+, and blackhole type route "
    "is stored in loopback",
)
def test_apply_route_with_route_type_multiple_times(eth1_up):
    routes = [
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.ROUTETYPE: Route.ROUTETYPE_BLACKHOLE,
        },
        {
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.ROUTETYPE: Route.ROUTETYPE_UNREACHABLE,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    _, routes_out_v4, _ = cmdlib.exec_cmd(
        "nmcli -g ipv4.routes con show lo".split(), check=True
    )
    _, routes_out_v6, _ = cmdlib.exec_cmd(
        "nmcli -g ipv6.routes con show lo".split(), check=True
    )
    assert routes_out_v4.count("blackhole") == 1
    assert routes_out_v6.count("unreachable") == 1


@pytest.mark.tier1
def test_add_gateway(eth1_up):
    routes = [_get_ipv4_gateways()[0], _get_ipv6_test_routes()[0]]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


def test_add_route_without_metric(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    for route in routes:
        del route[Route.METRIC]

    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


def test_add_route_without_table_id(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    for route in routes:
        del route[Route.TABLE_ID]

    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


def test_multiple_gateway(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: _get_ipv4_gateways() + _get_ipv6_gateways()
            },
        }
    )


@pytest.mark.tier1
def test_change_gateway(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    _get_ipv4_gateways()[0],
                    _get_ipv6_gateways()[0],
                ]
            },
        }
    )

    routes = [_get_ipv4_gateways()[1], _get_ipv6_gateways()[1]]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.STATE: Route.STATE_ABSENT,
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.DESTINATION: "0.0.0.0/0",
                    },
                    {
                        Route.STATE: Route.STATE_ABSENT,
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.DESTINATION: "::/0",
                    },
                ]
                + routes
            },
        }
    )

    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


def _get_ipv4_test_routes(nic="eth1"):
    return [
        {
            Route.DESTINATION: "198.51.100.0/24",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: nic,
            Route.TABLE_ID: IPV4_ROUTE_TABLE_ID1,
        },
        {
            Route.DESTINATION: "203.0.113.0/24",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: nic,
            Route.TABLE_ID: IPV4_ROUTE_TABLE_ID2,
        },
    ]


def _get_ipv4_gateways():
    return [
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: "192.0.2.2",
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
    ]


def _get_ipv6_test_routes(nic="eth1"):
    return [
        {
            Route.DESTINATION: "2001:db8:a::/64",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::a",
            Route.NEXT_HOP_INTERFACE: nic,
            Route.TABLE_ID: IPV6_ROUTE_TABLE_ID1,
        },
        {
            Route.DESTINATION: "2001:db8:b::/64",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::b",
            Route.NEXT_HOP_INTERFACE: nic,
            Route.TABLE_ID: IPV6_ROUTE_TABLE_ID2,
        },
    ]


def _get_ipv6_gateways():
    return [
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY1,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY2,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
    ]


parametrize_ip_ver_routes = pytest.mark.parametrize(
    "get_routes_func",
    [(_get_ipv4_test_routes), (_get_ipv6_test_routes)],
    ids=["ipv4", "ipv6"],
)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_remove_specific_route(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)

    absent_route = routes[0]
    absent_route[Route.STATE] = Route.STATE_ABSENT
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: [absent_route]},
        }
    )

    expected_routes = routes[1:]

    cur_state = libnmstate.show()
    assert_routes(expected_routes, cur_state)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_remove_wildcast_route_with_iface(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)

    absent_route = {
        Route.STATE: Route.STATE_ABSENT,
        Route.NEXT_HOP_INTERFACE: "eth1",
    }
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: [absent_route]},
        }
    )

    cur_state = libnmstate.show()
    assert_routes_missing(routes, cur_state)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_remove_wildcast_route_without_iface(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)

    absent_routes = []
    for route in routes:
        absent_routes.append(
            {
                Route.STATE: Route.STATE_ABSENT,
                Route.DESTINATION: route[Route.DESTINATION],
            }
        )
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: absent_routes},
        }
    )

    cur_state = libnmstate.show()
    assert_routes_missing(routes, cur_state)


# TODO: Once we can disable IPv6, we should add an IPv6 test case here
def test_disable_ipv4_with_routes_in_current(eth1_up):
    routes = _get_ipv4_test_routes()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    eth1_state = copy.deepcopy(ETH1_INTERFACE_STATE)
    eth1_state[Interface.IPV4] = {InterfaceIPv4.ENABLED: False}

    libnmstate.apply({Interface.KEY: [eth1_state]})

    cur_state = libnmstate.show()
    assert_routes_missing(routes, cur_state)


@pytest.mark.tier1
def test_disable_ipv4_and_remove_wildcard_route(eth1_up):
    routes = _get_ipv4_test_routes()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    eth1_state = copy.deepcopy(ETH1_INTERFACE_STATE)
    eth1_state[Interface.IPV4] = {InterfaceIPv4.ENABLED: False}

    absent_route = {
        Route.STATE: Route.STATE_ABSENT,
        Route.NEXT_HOP_INTERFACE: "eth1",
    }

    libnmstate.apply(
        {
            Interface.KEY: [eth1_state],
            Route.KEY: {Route.CONFIG: [absent_route]},
        }
    )

    cur_state = libnmstate.show()
    assert_routes_missing(routes, cur_state)


@pytest.mark.tier1
@parametrize_ip_ver_routes
def test_iface_down_with_routes_in_current(eth1_up, get_routes_func):
    routes = get_routes_func()
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.DOWN,
                }
            ]
        }
    )

    cur_state = libnmstate.show()
    assert_routes_missing(routes, cur_state)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 46,
    reason="Assigning static route to device without IP addresses is only "
    "support on NM 1.46+",
)
def test_static_route_with_empty_ip(eth1_up):
    eth1_state = copy.deepcopy(ETH1_INTERFACE_STATE)
    eth1_state[Interface.IPV4] = {
        InterfaceIPv4.DHCP: False,
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.ADDRESS: [],
    }
    eth1_state[Interface.IPV6] = {
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv4.ADDRESS: [],
    }
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS1,
            Route.TABLE_ID: 254,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV6_ADDRESS1,
            Route.TABLE_ID: 254,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [eth1_state],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


@pytest.fixture(scope="function")
def eth1_static_gateway_dns(eth1_up):
    routes = (
        [_get_ipv4_gateways()[0], _get_ipv6_gateways()[0]]
        + _get_ipv4_test_routes()
        + _get_ipv6_test_routes()
    )

    state = {
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {Route.CONFIG: routes},
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: [IPV6_DNS_NAMESERVER, IPV4_DNS_NAMESERVER],
                DNS.SEARCH: DNS_SEARCHES,
            }
        },
    }

    libnmstate.apply(state)
    yield state
    # Remove DNS config
    libnmstate.apply(
        {Interface.KEY: [], DNS.KEY: {DNS.CONFIG: {}}}, verify_change=False
    )


def test_apply_empty_state_preserve_routes(eth1_static_gateway_dns):
    pre_apply_state = libnmstate.show()

    libnmstate.apply({Interface.KEY: []})

    current_state = libnmstate.show()

    assert (
        current_state[Route.KEY][Route.CONFIG]
        == pre_apply_state[Route.KEY][Route.CONFIG]
    )
    assert (
        current_state[DNS.KEY][DNS.CONFIG]
        == pre_apply_state[DNS.KEY][DNS.CONFIG]
    )


def _get_routes_from_iproute(family, table):
    _, out, _ = cmdlib.exec_cmd(
        f"ip -{family} route show table {table}".split(), check=True
    )
    return out


def test_remove_default_ipv6_gateway_and_revert():
    gateway1 = {
        Route.DESTINATION: "::/0",
        Route.METRIC: -1,
        Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY1,
        Route.NEXT_HOP_INTERFACE: "eth1",
        Route.TABLE_ID: 0,
    }
    gateway2 = {
        Route.DESTINATION: "::/0",
        Route.METRIC: -1,
        Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY2,
        Route.NEXT_HOP_INTERFACE: "eth1",
        Route.TABLE_ID: 0,
    }

    eth1 = copy.deepcopy(ETH1_INTERFACE_STATE)
    d_state = {Interface.KEY: [eth1], Route.KEY: {Route.CONFIG: [gateway1]}}
    libnmstate.apply(d_state)

    gateway1[Route.STATE] = Route.STATE_ABSENT
    d_state[Route.KEY][Route.CONFIG] = [gateway1, gateway2]
    libnmstate.apply(d_state)

    gateway1.pop(Route.STATE)
    gateway2[Route.STATE] = Route.STATE_ABSENT
    libnmstate.apply(d_state)

    routes_output = _get_routes_from_iproute(6, "main")
    assert IPV6_GATEWAY1 in routes_output
    assert IPV6_GATEWAY2 not in routes_output


def test_add_and_remove_ipv4_link_local_route(eth1_static_gateway_dns):
    route2 = {
        Route.DESTINATION: IPV4_LINK_LOCAL_ROUTE,
        Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS2,
        Route.NEXT_HOP_INTERFACE: "eth1",
        Route.TABLE_ID: 100,
    }
    route3 = {
        Route.DESTINATION: IPV4_LINK_LOCAL_ROUTE,
        Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS3,
        Route.NEXT_HOP_INTERFACE: "eth1",
        Route.TABLE_ID: 100,
    }

    d_state = {Route.KEY: {Route.CONFIG: [route2]}}
    libnmstate.apply(d_state)

    route2[Route.STATE] = Route.STATE_ABSENT
    d_state[Route.KEY][Route.CONFIG] = [route2, route3]
    libnmstate.apply(d_state)

    routes_output = _get_routes_from_iproute(4, 100)
    assert IPV4_ADDRESS3 in routes_output
    assert IPV4_ADDRESS2 not in routes_output


@pytest.mark.tier1
def test_add_route_with_cwnd(eth1_up):
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS1,
            Route.CWND: 20,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY1,
            Route.CWND: 20,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


@pytest.mark.tier1
def test_delete_route_with_cwnd(eth1_up):
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS1,
            Route.CWND: 20,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY1,
            Route.CWND: 20,
        },
    ]
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {Route.CONFIG: routes},
        }
    )

    absent_routes = [{Route.CWND: 20, Route.STATE: Route.STATE_ABSENT}]
    libnmstate.apply({Route.KEY: {Route.CONFIG: absent_routes}})

    cur_state = libnmstate.show()
    assert_routes_missing(routes, cur_state)


@pytest.mark.tier1
def test_remove_and_add_route_with_cwnd(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.DESTINATION: IPV4_TEST_NET1,
                        Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS1,
                        Route.CWND: 20,
                    },
                    {
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.DESTINATION: IPV6_TEST_NET1,
                        Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY1,
                        Route.CWND: 20,
                    },
                ]
            },
        }
    )

    routes = [
        {Route.CWND: 20, Route.STATE: Route.STATE_ABSENT},
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS1,
            Route.CWND: 30,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV6_GATEWAY1,
            Route.CWND: 30,
        },
    ]
    libnmstate.apply({Route.KEY: {Route.CONFIG: routes}})

    expected_routes = routes[1:]
    cur_state = libnmstate.show()
    assert_routes(expected_routes, cur_state)


@pytest.mark.tier1
def test_route_cwnd_without_lock_means_cwnd_none(eth1_up):
    libnmstate.apply({Interface.KEY: [ETH1_INTERFACE_STATE]})
    cmdlib.exec_cmd(
        f"ip route add {IPV4_TEST_NET1} via {IPV4_ADDRESS1} "
        "dev eth1 cwnd 20".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"ip route add {IPV6_TEST_NET1} via {IPV6_GATEWAY1} "
        "dev eth1 cwnd 20".split(),
        check=True,
    )

    cur_state = libnmstate.show()

    for route in cur_state[Route.KEY][Route.CONFIG]:
        assert Route.CWND not in route or route[Route.CWND] != 20


@pytest.fixture(scope="function")
def route_rule_test_env(eth1_static_gateway_dns):
    yield eth1_static_gateway_dns


@pytest.mark.tier1
def test_route_rule_add_without_from_or_to_or_family(route_rule_test_env):
    state = route_rule_test_env
    state[RouteRule.KEY] = {
        RouteRule.CONFIG: [
            {RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1},
            {RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1},
        ]
    }

    with pytest.raises(NmstateValueError):
        libnmstate.apply(state)


@pytest.mark.tier1
def test_route_rule_add_from_only(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add_to_only(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add(static_eth1_with_route_rules):
    state = static_eth1_with_route_rules
    rules = state[RouteRule.KEY][RouteRule.CONFIG]
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add_without_priority(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_add_without_priority_apply_twice(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_add_without_route_table(route_rule_test_env):
    """
    When route table is not define in route rule, the main route table will
    be used.
    """
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.PRIORITY: 1000,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.PRIORITY: 1000,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_add_from_to_single_host(route_rule_test_env):
    """
    When route table is not define in route rule, the main route table will
    be used.
    """
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::",
            RouteRule.IP_TO: "2001:db8:f::/64",
        },
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::",
        },
        {RouteRule.IP_FROM: "203.0.113.1", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_add_with_auto_route_table_id(
    eth1_up,
):
    state = eth1_up
    rules = [
        {RouteRule.IP_FROM: "192.168.3.2/32", RouteRule.ROUTE_TABLE: 200},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    ipv4_state = state[Interface.KEY][0][Interface.IPV4]
    ipv4_state[InterfaceIPv4.ENABLED] = True
    ipv4_state[InterfaceIPv4.DHCP] = True
    ipv4_state[InterfaceIPv4.AUTO_ROUTE_TABLE_ID] = 200

    libnmstate.apply(state)
    _check_ip_rules(rules)


def test_route_rule_clear_state(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "203.0.113.1", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules = [{RouteRule.STATE: RouteRule.STATE_ABSENT}]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)

    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 0


def test_apply_empty_state_preserve_route_rules(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "203.0.113.1", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    _check_ip_rules(rules)

    libnmstate.apply({Interface.KEY: []})
    _check_ip_rules(rules)


def test_remove_route_rule_with_wildcard(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "203.0.113.1", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules = [
        {RouteRule.ROUTE_TABLE: 254, RouteRule.STATE: RouteRule.STATE_ABSENT}
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 0


def test_route_rule_remove_specific_rule(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "203.0.113.1/32", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules = [
        {
            RouteRule.IP_FROM: "203.0.113.1/32",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.STATE: RouteRule.STATE_ABSENT,
        }
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 1


def test_route_rule_clear_state_with_minimum_iface_state(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "203.0.113.1/32", RouteRule.IP_TO: "192.0.2.0/24"},
        {RouteRule.IP_FROM: "203.0.113.0/24", RouteRule.IP_TO: "192.0.2.1"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules = [{RouteRule.STATE: RouteRule.STATE_ABSENT}]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    state[Interface.KEY] = [{Interface.NAME: "eth1"}]
    libnmstate.apply(state)
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 0


def test_route_rule_clear_state_with_ipv6(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "2001:db8:a::", RouteRule.IP_TO: "2001:db8:f::/64"}
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules = [{RouteRule.STATE: RouteRule.STATE_ABSENT}]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 0


@pytest.mark.tier1
def test_route_rule_fwmark_without_fwmask(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:f::/64",
            RouteRule.FWMARK: 0x20,
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "192.0.2.0/24",
            RouteRule.FWMARK: 0x20,
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_fwmark_with_fwmask(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:f::/64",
            RouteRule.FWMARK: 0x20,
            RouteRule.FWMASK: 0x10,
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "192.0.2.0/24",
            RouteRule.FWMARK: 0x20,
            RouteRule.FWMASK: 0x10,
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_from_all_to_all(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
            RouteRule.PRIORITY: 100,
            RouteRule.FAMILY: RouteRule.FAMILY_IPV6,
        },
        {
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
            RouteRule.PRIORITY: 100,
            RouteRule.FAMILY: RouteRule.FAMILY_IPV4,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_from_all_to_all_ipv4(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
            RouteRule.PRIORITY: 100,
            RouteRule.FAMILY: RouteRule.FAMILY_IPV4,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules[0][RouteRule.FAMILY] = RouteRule.FAMILY_IPV6
    with pytest.raises(AssertionError):
        assert _check_ip_rules(rules)


@pytest.mark.tier1
def test_route_rule_from_all_to_all_ipv6(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
            RouteRule.PRIORITY: 100,
            RouteRule.FAMILY: RouteRule.FAMILY_IPV6,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    _check_ip_rules(rules)

    rules[0][RouteRule.FAMILY] = RouteRule.FAMILY_IPV4
    with pytest.raises(AssertionError):
        assert _check_ip_rules(rules)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 42, reason="Loopback is only support on NM 1.42+"
)
def test_route_rule_add_and_remove_using_loopback():
    desired_state = {
        RouteRule.KEY: {
            RouteRule.CONFIG: [
                {
                    RouteRule.IP_FROM: "192.0.2.0/24",
                    RouteRule.ROUTE_TABLE: 200,
                }
            ]
        }
    }

    libnmstate.apply(desired_state)
    _check_ip_rules(desired_state[RouteRule.KEY][RouteRule.CONFIG])

    desired_state[RouteRule.KEY][RouteRule.CONFIG][0][
        RouteRule.STATE
    ] = RouteRule.STATE_ABSENT
    libnmstate.apply(desired_state)


def _check_ip_rules(rules):
    for rule in rules:
        iprule.ip_rule_exist_in_os(rule)


def test_route_change_metric(eth1_static_gateway_dns):
    ipv4_route = _get_ipv4_gateways()[0]
    ipv4_route[Route.METRIC] += 1
    ipv6_route = _get_ipv6_gateways()[0]
    ipv6_route[Route.METRIC] += 2
    libnmstate.apply({Route.KEY: {Route.CONFIG: [ipv6_route, ipv4_route]}})


@pytest.fixture
def eth1_with_multipath_route(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
        }
    )
    cmdlib.exec_cmd(
        f"ip route add {IPV4_TEST_NET1} metric 500 "
        f"nexthop via {IPV4_ADDRESS2} dev eth1 onlink "
        f"nexthop via {IPV4_ADDRESS3} dev eth1 onlink".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"ip -6 route add {IPV6_TEST_NET1} metric 501 "
        f"nexthop via {IPV6_ADDRESS2} dev eth1 onlink "
        f"nexthop via {IPV6_ADDRESS3} dev eth1 onlink".split(),
        check=True,
    )
    yield
    cmdlib.exec_cmd(
        f"ip route del {IPV4_TEST_NET1} metric 500 "
        f"nexthop via {IPV4_ADDRESS2} dev eth1 onlink "
        f"nexthop via {IPV4_ADDRESS3} dev eth1 onlink".split()
    )
    cmdlib.exec_cmd(
        f"ip -6 route del {IPV6_TEST_NET1} metric 501 "
        f"nexthop via {IPV6_ADDRESS2} dev eth1 onlink "
        f"nexthop via {IPV6_ADDRESS3} dev eth1 onlink".split()
    )


def test_support_query_multipath_route(eth1_with_multipath_route):
    cur_state = libnmstate.show()
    expected_routes = [
        {
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.METRIC: 500,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS2,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
            Route.WEIGHT: 1,
        },
        {
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.METRIC: 500,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS3,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
            Route.WEIGHT: 1,
        },
        {
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.METRIC: 501,
            Route.NEXT_HOP_ADDRESS: IPV6_ADDRESS2,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
        {
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.METRIC: 501,
            Route.NEXT_HOP_ADDRESS: IPV6_ADDRESS3,
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.TABLE_ID: 254,
        },
    ]
    cur_state = libnmstate.show()
    assert_routes(expected_routes, cur_state)


@pytest.fixture
def br_with_static_route():
    with linux_bridge(
        name=TEST_BRIDGE0,
        bridge_subtree_state={},
        extra_iface_state={
            Interface.IPV4: {
                InterfaceIPv4.ADDRESS: [
                    {
                        InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                        InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                    }
                ],
                InterfaceIPv4.DHCP: False,
                InterfaceIPv4.ENABLED: True,
            },
            Interface.IPV6: {
                InterfaceIPv6.ADDRESS: [
                    {
                        InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                    }
                ],
                InterfaceIPv6.DHCP: False,
                InterfaceIPv6.AUTOCONF: False,
                InterfaceIPv6.ENABLED: True,
            },
        },
        create=False,
    ) as desired_state:
        routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
        for route in routes:
            route[Route.NEXT_HOP_INTERFACE] = TEST_BRIDGE0
        desired_state[Route.KEY] = {Route.CONFIG: routes}
        libnmstate.apply(desired_state)
        yield


@pytest.mark.tier1
def test_delete_both_route_and_interface(br_with_static_route):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ],
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.NEXT_HOP_INTERFACE: TEST_BRIDGE0,
                        Route.STATE: Route.STATE_ABSENT,
                    }
                ]
            },
        }
    )
    assertlib.assert_absent(TEST_BRIDGE0)


@pytest.fixture
def br_with_static_route_rule(
    br_with_static_route,
):
    libnmstate.apply(
        {
            RouteRule.KEY: {
                RouteRule.CONFIG: [
                    {
                        RouteRule.IP_FROM: "192.168.3.0/24",
                        RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
                    },
                    {
                        RouteRule.IP_FROM: "2001:db8:f::",
                        RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
                    },
                ]
            }
        }
    )
    yield


@pytest.mark.tier1
def test_delete_both_route_rule_and_interface(br_with_static_route_rule):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ],
            RouteRule.KEY: {
                RouteRule.CONFIG: [
                    {
                        RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
                        RouteRule.STATE: Route.STATE_ABSENT,
                    },
                    {
                        RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
                        RouteRule.STATE: Route.STATE_ABSENT,
                    },
                ]
            },
        }
    )
    assertlib.assert_absent(TEST_BRIDGE0)


def test_ignore_route_metric_difference(eth1_static_gateway_dns):
    dup_routes = [_get_ipv4_test_routes()[0], _get_ipv6_test_routes()[0]]
    dup_routes[0][Route.METRIC] += 1
    dup_routes[1][Route.METRIC] += 1
    libnmstate.apply({Route.KEY: {Route.CONFIG: dup_routes}})

    cur_state = libnmstate.show()
    # Ensure duplicate route(only metric difference) is removed
    cur_routes = [
        route
        for route in cur_state[Route.KEY][Route.CONFIG]
        if route[Route.DESTINATION] == dup_routes[0][Route.DESTINATION]
        or route[Route.DESTINATION] == dup_routes[1][Route.DESTINATION]
    ]
    assert len(cur_routes) == 2


@pytest.fixture
def eth1_static_ip(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [ETH1_INTERFACE_STATE],
        }
    )
    yield


def test_sanitize_route_destination(eth1_static_ip):
    desired_routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    desired_routes[0][Route.DESTINATION] = "198.51.100.1/24"
    desired_routes[1][Route.DESTINATION] = "203.0.113.1"
    desired_routes[2][Route.DESTINATION] = "2001:db8:a::1/64"
    desired_routes[3][Route.DESTINATION] = "2001:db8:b::0001"
    libnmstate.apply({Route.KEY: {Route.CONFIG: desired_routes}})

    expected_routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    expected_routes[1][Route.DESTINATION] = "203.0.113.1/32"
    expected_routes[3][Route.DESTINATION] = "2001:db8:b::1/128"

    cur_state = libnmstate.show()
    assert_routes(expected_routes, cur_state)


def test_sanitize_route_rule_from_to(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {RouteRule.IP_FROM: "203.0.113.1", RouteRule.IP_TO: "192.0.2.4/24"},
        {RouteRule.IP_FROM: "2001:db8::1", RouteRule.IP_TO: "2001:db8::f/64"},
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}
    libnmstate.apply(state)

    expected_rules = [
        {RouteRule.IP_FROM: "203.0.113.1/32", RouteRule.IP_TO: "192.0.2.0/24"},
        {
            RouteRule.IP_FROM: "2001:db8::1/128",
            RouteRule.IP_TO: "2001:db8::/64",
        },
    ]
    _check_ip_rules(expected_rules)


@pytest.fixture
def static_route_with_additional_bgp_route(eth1_static_gateway_dns):
    cmdlib.exec_cmd(
        f"ip route add {BGP_ROUTE_DST_V4} "
        f"dev eth1 proto {BGP_PROTOCOL_ID}".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"ip route add {BGP_ROUTE_DST_V6} "
        f"dev eth1 proto {BGP_PROTOCOL_ID}".split(),
        check=True,
    )
    yield


def test_do_not_show_bgp_route(static_route_with_additional_bgp_route):
    routes = libnmstate.show()[Route.KEY][Route.RUNNING]
    for route in routes:
        assert route[Route.DESTINATION] != BGP_ROUTE_DST_V4
        assert route[Route.DESTINATION] != BGP_ROUTE_DST_V6


@pytest.mark.tier1
def test_route_rule_iif(route_rule_test_env):
    desired_rules = [
        {
            RouteRule.IIF: "eth1",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
            RouteRule.IP_FROM: IPV4_TEST_NET1,
        },
        {
            RouteRule.IIF: "eth1",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
            RouteRule.IP_FROM: IPV6_TEST_NET1,
        },
    ]

    libnmstate.apply({RouteRule.KEY: {RouteRule.CONFIG: desired_rules}})
    _check_ip_rules(desired_rules)


@pytest.mark.tier1
def test_route_rule_action(route_rule_test_env):
    desired_rules = [
        {
            RouteRule.PRIORITY: 10000,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "192.0.2.1/32",
            RouteRule.ACTION: RouteRule.ACTION_BLACKHOLE,
        },
        {
            RouteRule.PRIORITY: 10001,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "192.0.2.2/32",
            RouteRule.ACTION: RouteRule.ACTION_UNREACHABLE,
        },
        {
            RouteRule.PRIORITY: 10002,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "192.0.2.3/32",
            RouteRule.ACTION: RouteRule.ACTION_PROHIBIT,
        },
        {
            RouteRule.PRIORITY: 20000,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "2001:db8:1::1/128",
            RouteRule.ACTION: RouteRule.ACTION_BLACKHOLE,
        },
        {
            RouteRule.PRIORITY: 20001,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "2001:db8:1::2/128",
            RouteRule.ACTION: RouteRule.ACTION_UNREACHABLE,
        },
        {
            RouteRule.PRIORITY: 20002,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "2001:db8:1::3/128",
            RouteRule.ACTION: RouteRule.ACTION_PROHIBIT,
        },
    ]

    libnmstate.apply({RouteRule.KEY: {RouteRule.CONFIG: desired_rules}})
    _check_ip_rules(desired_rules)


def test_gen_conf_route_rule(eth1_up):
    desired_rules = [
        {
            RouteRule.PRIORITY: 10000,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "192.0.2.1/32",
            RouteRule.ACTION: RouteRule.ACTION_BLACKHOLE,
        },
        {
            RouteRule.PRIORITY: 10001,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "192.0.2.2/32",
            RouteRule.ACTION: RouteRule.ACTION_UNREACHABLE,
        },
        {
            RouteRule.PRIORITY: 10002,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "192.0.2.3/32",
            RouteRule.ACTION: RouteRule.ACTION_PROHIBIT,
        },
        {
            RouteRule.PRIORITY: 20000,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "2001:db8:1::1/128",
            RouteRule.ACTION: RouteRule.ACTION_BLACKHOLE,
        },
        {
            RouteRule.PRIORITY: 20001,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "2001:db8:1::2/128",
            RouteRule.ACTION: RouteRule.ACTION_UNREACHABLE,
        },
        {
            RouteRule.PRIORITY: 20002,
            RouteRule.IIF: "eth1",
            RouteRule.IP_FROM: "2001:db8:1::3/128",
            RouteRule.ACTION: RouteRule.ACTION_PROHIBIT,
        },
    ]

    routes = (
        [_get_ipv4_gateways()[0], _get_ipv6_gateways()[0]]
        + _get_ipv4_test_routes()
        + _get_ipv6_test_routes()
    )

    desired_state = {
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {Route.CONFIG: routes},
        RouteRule.KEY: {RouteRule.CONFIG: copy.deepcopy(desired_rules)},
    }

    with gen_conf_apply(desired_state):
        _check_ip_rules(desired_rules)


@pytest.fixture
def static_eth1_with_route_rules(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.PRIORITY: 1000,
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.PRIORITY: 1000,
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    yield state


@pytest.fixture
def static_eth1_with_empty_ip_from_to_route_rules(
    static_eth1_with_route_rules,
):
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:b::/64",
            RouteRule.PRIORITY: 999,
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_TO: "192.0.2.9",
            RouteRule.PRIORITY: 999,
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state = {RouteRule.KEY: {RouteRule.CONFIG: rules}}
    libnmstate.apply(state)
    yield


def test_absent_route_rule_with_empty_ip_from_to(
    static_eth1_with_empty_ip_from_to_route_rules,
):
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 4

    rules = [
        {
            RouteRule.STATE: RouteRule.STATE_ABSENT,
            RouteRule.IP_TO: "",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.STATE: RouteRule.STATE_ABSENT,
            RouteRule.IP_FROM: "",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
    ]
    state = {RouteRule.KEY: {RouteRule.CONFIG: rules}}
    libnmstate.apply(state)
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 2


@pytest.fixture
def static_eth1_with_routes(eth1_up):
    routes = _get_ipv4_test_routes() + _get_ipv6_test_routes()
    state = {
        Interface.KEY: [ETH1_INTERFACE_STATE],
        Route.KEY: {Route.CONFIG: routes},
    }
    libnmstate.apply(state)
    yield state


def test_absent_route_with_invalid_empty_destination(static_eth1_with_routes):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            {
                Route.KEY: {
                    Route.CONFIG: [
                        {
                            Route.NEXT_HOP_INTERFACE: "eth1",
                            Route.STATE: Route.STATE_ABSENT,
                            Route.DESTINATION: "",
                        },
                    ]
                },
            }
        )


@pytest.mark.tier1
def test_preserve_unmanaged_routes(eth1_static_ip):
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_DEFAULT_GATEWAY,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS2,
            Route.WEIGHT: 1,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_DEFAULT_GATEWAY,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS3,
            Route.WEIGHT: 256,
        },
    ]
    libnmstate.apply(
        {
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)

    cmdlib.exec_cmd(
        f"ip route add {IPV4_TEST_NET1} via {IPV4_ADDRESS1} "
        "dev eth1 proto bird metric 50".split(),
        check=True,
    )

    libnmstate.apply(
        {
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)
    routes_output4 = _get_routes_from_iproute(4, "main")
    assert f"{IPV4_TEST_NET1} via {IPV4_ADDRESS1}" in routes_output4


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 41, reason="ECMP route is only support on NM 1.41+"
)
def test_add_and_remove_ecmp_route(eth1_static_ip):
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_DEFAULT_GATEWAY,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS2,
            Route.WEIGHT: 1,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_DEFAULT_GATEWAY,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS3,
            Route.WEIGHT: 256,
        },
    ]
    libnmstate.apply(
        {
            Route.KEY: {Route.CONFIG: routes},
        }
    )
    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)

    for route in routes:
        route[Route.STATE] = Route.STATE_ABSENT

    libnmstate.apply(
        {
            Route.KEY: {Route.CONFIG: routes},
        }
    )


@pytest.fixture
def static_eth1_with_default_priority_route_rules(route_rule_test_env):
    state = route_rule_test_env
    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:a::/64",
            RouteRule.IP_TO: "2001:db8:f::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.0/24",
            RouteRule.IP_TO: "192.0.2.0/24",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state[RouteRule.KEY] = {RouteRule.CONFIG: rules}

    libnmstate.apply(state)
    yield state


def test_auto_choose_route_rule_priority(
    static_eth1_with_default_priority_route_rules,
):
    current_state = libnmstate.show()
    original_rules = current_state[RouteRule.KEY][RouteRule.CONFIG]
    assert len(original_rules) == 2

    rules = [
        {
            RouteRule.IP_FROM: "2001:db8:b::/64",
            RouteRule.IP_TO: "2001:db8:e::/64",
            RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
        },
        {
            RouteRule.IP_FROM: "203.0.113.2",
            RouteRule.IP_TO: "192.0.2.2",
            RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
        },
    ]
    state = {RouteRule.KEY: {RouteRule.CONFIG: rules}}

    libnmstate.apply(state)
    current_state = libnmstate.show()
    assert len(current_state[RouteRule.KEY][RouteRule.CONFIG]) == 4
    rules[0][RouteRule.PRIORITY] = 30002
    rules[1][RouteRule.PRIORITY] = 30003
    _check_ip_rules(rules)
    original_rules[0][RouteRule.PRIORITY] = 30000
    original_rules[1][RouteRule.PRIORITY] = 30001
    _check_ip_rules(original_rules)


def test_add_routes_to_local_route_table_255(static_eth1_with_routes):
    routes = [
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV4_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS2,
            Route.TABLE_ID: 255,
        },
        {
            Route.NEXT_HOP_INTERFACE: "eth1",
            Route.DESTINATION: IPV6_TEST_NET1,
            Route.NEXT_HOP_ADDRESS: IPV6_ADDRESS2,
            Route.TABLE_ID: 255,
        },
    ]

    state = {Route.KEY: {Route.CONFIG: routes}}
    libnmstate.apply(state)

    cur_state = libnmstate.show()
    assert_routes(routes, cur_state)


@pytest.fixture
def static_eth1_eth2_with_routes_on_same_table_id(
    eth1_up,
    eth2_up,
):
    routes = _get_ipv4_test_routes("eth1") + _get_ipv6_test_routes("eth2")
    for route in routes:
        route[Route.TABLE_ID] = TEST_ROUTE_TABLE_ID
    eth1_state = copy.deepcopy(ETH1_INTERFACE_STATE)
    eth1_state.pop(Interface.IPV6)
    eth2_state = copy.deepcopy(ETH1_INTERFACE_STATE)
    eth2_state[Interface.NAME] = "eth2"
    eth2_state.pop(Interface.IPV4)
    state = {
        Interface.KEY: [eth1_state, eth2_state],
        Route.KEY: {Route.CONFIG: routes},
    }
    libnmstate.apply(state)
    yield


def test_add_route_rules_with_the_same_route_table_id_on_diff_ip_stack(
    static_eth1_eth2_with_routes_on_same_table_id,
):
    desired_state = {
        RouteRule.KEY: {
            RouteRule.CONFIG: [
                {
                    RouteRule.IP_FROM: "2001:db8:f::/64",
                    RouteRule.ROUTE_TABLE: TEST_ROUTE_TABLE_ID,
                },
                {
                    RouteRule.IP_FROM: "192.0.2.0/24",
                    RouteRule.ROUTE_TABLE: TEST_ROUTE_TABLE_ID,
                },
            ]
        }
    }
    libnmstate.apply(desired_state)


def test_route_rule_suppress_prefix_length(route_rule_test_env):
    desired_state = {
        RouteRule.KEY: {
            RouteRule.CONFIG: [
                {
                    RouteRule.IP_FROM: "2001:db8:f::/64",
                    RouteRule.SUPPRESS_PREFIX_LENGTH: 1,
                    RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
                },
                {
                    RouteRule.IP_FROM: "192.0.2.0/24",
                    RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
                    RouteRule.SUPPRESS_PREFIX_LENGTH: 0,
                },
            ]
        }
    }
    libnmstate.apply(desired_state)
    _check_ip_rules(desired_state[RouteRule.KEY][RouteRule.CONFIG])


def test_append_route_rule(route_rule_test_env):
    desired_state = {
        RouteRule.KEY: {
            RouteRule.CONFIG: [
                {
                    RouteRule.IP_FROM: "2001:db8:f::/64",
                    RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
                },
                {
                    RouteRule.IP_FROM: "192.0.2.1/32",
                    RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
                },
            ]
        }
    }
    libnmstate.apply(desired_state)
    _check_ip_rules(desired_state[RouteRule.KEY][RouteRule.CONFIG])

    new_desired_state = {
        RouteRule.KEY: {
            RouteRule.CONFIG: [
                {
                    RouteRule.IP_FROM: "2001:db8:e::/64",
                    RouteRule.ROUTE_TABLE: IPV6_ROUTE_TABLE_ID1,
                },
                {
                    RouteRule.IP_FROM: "192.0.2.2/32",
                    RouteRule.ROUTE_TABLE: IPV4_ROUTE_TABLE_ID1,
                },
            ]
        },
        Interface.KEY: [ETH1_INTERFACE_STATE],
    }

    libnmstate.apply(new_desired_state)
    _check_ip_rules(
        desired_state[RouteRule.KEY][RouteRule.CONFIG]
        + new_desired_state[RouteRule.KEY][RouteRule.CONFIG]
    )


@pytest.fixture
def cleanup_veth1_kernel_mode():
    with disable_service("NetworkManager"):
        yield
        desired_state = load_yaml(
            """---
            interfaces:
            - name: veth1
              type: veth
              state: absent
            """
        )
        libnmstate.apply(desired_state, kernel_only=True)


def test_kernel_mode_static_route_and_remove(cleanup_veth1_kernel_mode):
    desired_state = load_yaml(
        """---
        interfaces:
        - name: veth1
          type: veth
          state: up
          veth:
            peer: veth1_peer
          ipv4:
            address:
            - ip: 192.0.2.251
              prefix-length: 24
            dhcp: false
            enabled: true
          ipv6:
            enabled: true
            autoconf: false
            dhcp: false
            address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        routes:
         config:
           - destination: 0.0.0.0/0
             next-hop-address: 192.0.2.1
             next-hop-interface: veth1
             metric: 109
           - destination: ::/0
             next-hop-address: 2001:db8:1::2
             next-hop-interface: veth1
             metric: 102
        """
    )
    libnmstate.apply(desired_state, kernel_only=True)

    cur_state = libnmstate.show(kernel_only=True)
    assert_routes(
        desired_state[Route.KEY][Route.CONFIG], cur_state, nic="veth1"
    )

    new_state = load_yaml(
        """---
        routes:
         config:
           - state: absent
             next-hop-interface: veth1
        """
    )
    libnmstate.apply(new_state, kernel_only=True)

    cur_state = libnmstate.show(kernel_only=True)
    assert_routes_missing(
        desired_state[Route.KEY][Route.CONFIG], cur_state, nic="veth1"
    )
