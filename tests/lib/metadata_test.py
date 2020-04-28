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

from unittest import mock

from libnmstate import metadata
from libnmstate import state
from libnmstate.nm import dns as nm_dns
from libnmstate.error import NmstateValueError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route
from libnmstate.schema import RouteRule


TYPE_BOND = InterfaceType.BOND

BOND_NAME = "bond99"
TEST_IFACE1 = "eth1"


@pytest.fixture(autouse=True)
def nm_mock():
    with mock.patch.object(metadata, "nm") as m:
        yield m


@pytest.fixture
def nm_dns_mock(nm_mock):
    nm_mock.dns.find_interfaces_for_name_servers.return_value = (
        TEST_IFACE1,
        TEST_IFACE1,
    )
    nm_mock.dns.DNS_METADATA_PRIORITY = nm_dns.DNS_METADATA_PRIORITY
    nm_mock.dns.DNS_PRIORITY_STATIC_BASE = nm_dns.DNS_PRIORITY_STATIC_BASE
    return


class TestDesiredStateMetadata:
    def test_empty_states(self):
        desired_state = state.State({})
        current_state = state.State({})

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state.state == {Interface.KEY: []}
        assert current_state.state == {Interface.KEY: []}


class TestDesiredStateBondMetadata:
    def test_bond_creation_with_new_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        current_state = state.State({})
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_BOND

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state.state == expected_dstate.state
        assert current_state == expected_cstate

    def test_bond_creation_with_existing_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"])
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "eth0",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {
            Interface.NAME: "eth0",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces["eth1"] = {
            Interface.NAME: "eth1",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth1"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_BOND

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_editing_option(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: BOND_NAME,
                        Interface.TYPE: TYPE_BOND,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_adding_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth1",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "eth0",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    }
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {
            Interface.NAME: "eth0",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_BOND

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_removing_slaves(self):
        desired_state = state.State(
            {Interface.KEY: [create_bond_state_dict(BOND_NAME, ["eth0"])]}
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.ETHERNET,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.ETHERNET,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {
            Interface.NAME: "eth0",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces["eth1"] = {Interface.NAME: "eth1"}

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_edit_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "eth0",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                        "fookey": "fooval",
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_reusing_slave_used_by_existing_bond(self):
        BOND2_NAME = "bond88"
        desired_state = state.State(
            {Interface.KEY: [create_bond_state_dict(BOND2_NAME, ["eth0"])]}
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {
            Interface.NAME: "eth0",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND2_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_swap_slaves_between_bonds(self):
        BOND2_NAME = "bond88"
        desired_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth1"]),
                    create_bond_state_dict(BOND2_NAME, ["eth0"]),
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0"]),
                    create_bond_state_dict(BOND2_NAME, ["eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {
            Interface.NAME: "eth0",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth1"] = {
            Interface.NAME: "eth1",
            Interface.STATE: InterfaceState.UP,
        }
        expected_dstate.interfaces["eth0"][metadata.MASTER] = BOND2_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces["eth1"][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_BOND

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_remove_bond_while_keeping_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: BOND_NAME,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                    {
                        Interface.NAME: "eth0",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    create_bond_state_dict(BOND_NAME, ["eth0", "eth1"]),
                    {
                        Interface.NAME: "eth0",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                    {
                        Interface.NAME: "eth1",
                        Interface.STATE: InterfaceState.UP,
                        Interface.TYPE: InterfaceType.UNKNOWN,
                    },
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert desired_state == expected_dstate
        assert current_state == expected_cstate


def create_bond_state_dict(name, slaves=None):
    slaves = slaves or []
    return {
        Interface.NAME: name,
        Interface.TYPE: TYPE_BOND,
        Interface.STATE: InterfaceState.UP,
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.SLAVES: slaves,
        },
    }


class TestRouteMetadata:
    def test_with_empty_states(self):
        desired_state = state.State({})
        current_state = state.State({})

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert {} == desired_state.interfaces

    def test_no_routes_with_no_interfaces(self):
        desired_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}}
        )
        current_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}}
        )

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert {} == desired_state.interfaces

    def test_route_with_no_desired_or_current_interfaces(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: [route0.to_dict()]}}
        )
        current_state = state.State({})

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert {} == desired_state.interfaces

    def test_route_with_no_desired_or_current_matching_interface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state("foo")],
                Route.KEY: {Route.CONFIG: [route0.to_dict()]},
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state("boo")],
                Route.KEY: {Route.CONFIG: []},
            }
        )

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert "foo" in desired_state.interfaces
        assert metadata.ROUTES not in desired_state.interfaces["foo"]

    def test_route_with_matching_desired_interface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {Route.CONFIG: [route0.to_dict()]},
            }
        )
        current_state = state.State({})

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        iface_state = desired_state.interfaces["eth1"]
        (route_metadata,) = iface_state[Interface.IPV4][metadata.ROUTES]
        assert route0.to_dict() == route_metadata

    def test_route_with_matching_current_interface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: [route0.to_dict()]}}
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {Route.CONFIG: []},
            }
        )

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        iface_state = desired_state.interfaces["eth1"]
        (route_metadata,) = iface_state[Interface.IPV4][metadata.ROUTES]
        assert route0.to_dict() == route_metadata

    def test_two_routes_with_matching_interfaces(self):
        route0 = self._create_route0()
        route1 = self._create_route1()
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {
                    Route.CONFIG: [route0.to_dict(), route1.to_dict()]
                },
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth2")],
                Route.KEY: {Route.CONFIG: []},
            }
        )

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        iface0_state = desired_state.interfaces["eth1"]
        iface1_state = desired_state.interfaces["eth2"]
        (route0_metadata,) = iface0_state[Interface.IPV4][metadata.ROUTES]
        (route1_metadata,) = iface1_state[Interface.IPV6][metadata.ROUTES]
        assert route0.to_dict() == route0_metadata
        assert route1.to_dict() == route1_metadata

    def _create_route0(self):
        return _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)

    def _create_route1(self):
        return _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )


def _create_interface_state(iface_name):
    return {
        Interface.NAME: iface_name,
        Interface.TYPE: InterfaceType.ETHERNET,
        Interface.IPV4: {},
        Interface.IPV6: {},
    }


def _create_route(dest, via_addr, via_iface, table, metric):
    return state.RouteEntry(
        {
            Route.DESTINATION: dest,
            Route.METRIC: metric,
            Route.NEXT_HOP_ADDRESS: via_addr,
            Route.NEXT_HOP_INTERFACE: via_iface,
            Route.TABLE_ID: table,
        }
    )


def test_dns_metadata_empty():
    desired_state = state.State(
        {Interface.KEY: _get_test_iface_states(), Route.KEY: {}, DNS.KEY: {}}
    )
    current_state = state.State({})

    nmclient = mock.MagicMock()
    metadata.generate_ifaces_metadata(nmclient, desired_state, current_state)
    assert (
        nm_dns.DNS_METADATA
        not in desired_state.interfaces[TEST_IFACE1][Interface.IPV4]
    )
    assert (
        nm_dns.DNS_METADATA
        not in desired_state.interfaces[TEST_IFACE1][Interface.IPV6]
    )


def test_dns_gen_metadata_static_gateway_ipv6_name_server_before_ipv4(
    nm_dns_mock,
):
    dns_config = {
        DNS.SERVER: ["2001:4860:4860::8888", "8.8.8.8"],
        DNS.SEARCH: ["example.org", "example.com"],
    }

    desired_state = state.State(
        {
            Interface.KEY: _get_test_iface_states(),
            Route.KEY: {Route.CONFIG: _gen_default_gateway_route(TEST_IFACE1)},
            DNS.KEY: {DNS.CONFIG: dns_config},
        }
    )
    current_state = state.State({})

    nmclient = mock.MagicMock()
    metadata.generate_ifaces_metadata(nmclient, desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ["8.8.8.8"],
        DNS.SEARCH: [],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE + 1,
    }
    ipv6_dns_config = {
        DNS.SERVER: ["2001:4860:4860::8888"],
        DNS.SEARCH: ["example.org", "example.com"],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE,
    }
    iface_state = desired_state.interfaces[TEST_IFACE1]
    assert ipv4_dns_config == iface_state[Interface.IPV4][nm_dns.DNS_METADATA]
    assert ipv6_dns_config == iface_state[Interface.IPV6][nm_dns.DNS_METADATA]


def test_dns_gen_metadata_static_gateway_ipv6_name_server_after_ipv4(
    nm_dns_mock,
):
    dns_config = {
        DNS.SERVER: ["8.8.8.8", "2001:4860:4860::8888"],
        DNS.SEARCH: ["example.org", "example.com"],
    }

    desired_state = state.State(
        {
            Interface.KEY: _get_test_iface_states(),
            Route.KEY: {Route.CONFIG: _gen_default_gateway_route(TEST_IFACE1)},
            DNS.KEY: {DNS.CONFIG: dns_config},
        }
    )
    current_state = state.State({})

    nmclient = mock.MagicMock()
    metadata.generate_ifaces_metadata(nmclient, desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ["8.8.8.8"],
        DNS.SEARCH: ["example.org", "example.com"],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE,
    }
    ipv6_dns_config = {
        DNS.SERVER: ["2001:4860:4860::8888"],
        DNS.SEARCH: [],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE + 1,
    }
    iface_state = desired_state.interfaces[TEST_IFACE1]
    assert ipv4_dns_config == iface_state[Interface.IPV4][nm_dns.DNS_METADATA]
    assert ipv6_dns_config == iface_state[Interface.IPV6][nm_dns.DNS_METADATA]


def test_dns_metadata_interface_not_included_in_desire(nm_dns_mock):
    dns_config = {
        DNS.SERVER: ["2001:4860:4860::8888", "8.8.8.8"],
        DNS.SEARCH: ["example.org", "example.com"],
    }

    desired_state = state.State(
        {
            Interface.KEY: [],
            Route.KEY: {Route.CONFIG: _gen_default_gateway_route(TEST_IFACE1)},
            DNS.KEY: {DNS.CONFIG: dns_config},
        }
    )
    current_state = state.State(
        {
            Interface.KEY: _get_test_iface_states(),
            Route.KEY: {Route.CONFIG: _gen_default_gateway_route(TEST_IFACE1)},
        }
    )
    nmclient = mock.MagicMock()
    metadata.generate_ifaces_metadata(nmclient, desired_state, current_state)
    iface_state = desired_state.interfaces[TEST_IFACE1]
    ipv4_dns_config = {
        DNS.SERVER: ["8.8.8.8"],
        DNS.SEARCH: [],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE + 1,
    }
    ipv6_dns_config = {
        DNS.SERVER: ["2001:4860:4860::8888"],
        DNS.SEARCH: ["example.org", "example.com"],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE,
    }
    assert ipv4_dns_config == iface_state[Interface.IPV4][nm_dns.DNS_METADATA]
    assert ipv6_dns_config == iface_state[Interface.IPV6][nm_dns.DNS_METADATA]


def _get_test_iface_states():
    return [
        {
            Interface.NAME: TEST_IFACE1,
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


def _gen_default_gateway_route(iface_name):
    return [
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 200,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.NEXT_HOP_INTERFACE: iface_name,
            Route.TABLE_ID: 54,
        },
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 201,
            Route.NEXT_HOP_ADDRESS: "2001:db8:2::f",
            Route.NEXT_HOP_INTERFACE: iface_name,
            Route.TABLE_ID: 54,
        },
    ]


class TestRouteRuleMetadata:
    TEST_ROUTE_TABLE = 50

    def test_with_empty_states(self):
        desired_state = state.State({})
        current_state = state.State({})

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert {} == desired_state.interfaces

    def test_no_rules_with_no_interfaces(self):
        desired_state = state.State(
            {Interface.KEY: [], RouteRule.KEY: {RouteRule.CONFIG: []}}
        )
        current_state = state.State(
            {Interface.KEY: [], RouteRule.KEY: {RouteRule.CONFIG: []}}
        )

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        assert {} == desired_state.interfaces

    def test_rule_with_no_route(self):
        rule0 = self._create_rule0()
        desired_state = state.State(
            {
                Route.KEY: {Route.CONFIG: []},
                RouteRule.KEY: {RouteRule.CONFIG: [rule0.to_dict()]},
            }
        )
        current_state = state.State({})

        with pytest.raises(NmstateValueError):
            nmclient = mock.MagicMock()
            metadata.generate_ifaces_metadata(
                nmclient, desired_state, current_state
            )

    def test_rule_with_no_matching_route_table(self):
        rule0 = self._create_rule0()
        route = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            TestRouteRuleMetadata.TEST_ROUTE_TABLE + 1,
            103,
        )
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {Route.CONFIG: [route.to_dict()]},
                RouteRule.KEY: {RouteRule.CONFIG: [rule0.to_dict()]},
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {Route.CONFIG: [route.to_dict()]},
            }
        )
        rule0 = self._create_rule0()
        route = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            TestRouteRuleMetadata.TEST_ROUTE_TABLE + 1,
            103,
        )
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {Route.CONFIG: [route.to_dict()]},
                RouteRule.KEY: {RouteRule.CONFIG: [rule0.to_dict()]},
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {Route.CONFIG: [route.to_dict()]},
            }
        )

        with pytest.raises(NmstateValueError):
            nmclient = mock.MagicMock()
            metadata.generate_ifaces_metadata(
                nmclient, desired_state, current_state
            )

    def test_rule_with_matching_route_table(self):
        rule0 = self._create_rule0()
        rule1 = self._create_rule1()
        route0 = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            TestRouteRuleMetadata.TEST_ROUTE_TABLE,
            103,
        )
        route1 = _create_route(
            "2001:db8:f::/64",
            "2001:db8:e::",
            "eth1",
            TestRouteRuleMetadata.TEST_ROUTE_TABLE,
            103,
        )
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state("eth1")],
                Route.KEY: {
                    Route.CONFIG: [route0.to_dict(), route1.to_dict()]
                },
                RouteRule.KEY: {
                    RouteRule.CONFIG: [rule0.to_dict(), rule1.to_dict()]
                },
            }
        )
        current_state = state.State({})

        nmclient = mock.MagicMock()
        metadata.generate_ifaces_metadata(
            nmclient, desired_state, current_state
        )

        iface_state = desired_state.interfaces["eth1"]
        (rule0_metadata,) = iface_state[Interface.IPV4][
            metadata.ROUTE_RULES_METADATA
        ]
        (rule1_metadata,) = iface_state[Interface.IPV6][
            metadata.ROUTE_RULES_METADATA
        ]
        assert rule0.to_dict() == rule0_metadata
        assert rule1.to_dict() == rule1_metadata

    def _create_rule0(self):
        return _create_rule(
            "198.51.100.0/24",
            "192.0.2.1",
            103,
            TestRouteRuleMetadata.TEST_ROUTE_TABLE,
        )

    def _create_rule1(self):
        return _create_rule(
            "2001:db8:a::/64",
            "2001:db8:1::a",
            104,
            TestRouteRuleMetadata.TEST_ROUTE_TABLE,
        )


def _create_rule(ip_from, ip_to, priority, table):
    return state.RouteRuleEntry(
        {
            RouteRule.IP_FROM: ip_from,
            RouteRule.IP_TO: ip_to,
            RouteRule.PRIORITY: priority,
            RouteRule.ROUTE_TABLE: table,
        }
    )
