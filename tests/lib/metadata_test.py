#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import pytest

from .compat import mock

from libnmstate import metadata
from libnmstate import state
from libnmstate.nm import dns as nm_dns
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import OVSBridgePortType as OBPortType
from libnmstate.schema import Route


TYPE_BOND = InterfaceType.BOND
TYPE_OVS_BR = InterfaceType.OVS_BRIDGE

BOND_NAME = 'bond99'
OVS_NAME = 'ovs-br99'
TEST_IFACE1 = 'eth1'


@pytest.fixture(autouse=True)
def nm_mock():
    with mock.patch.object(metadata, 'nm') as m:
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


class TestDesiredStateMetadata(object):
    def test_empty_states(self):
        desired_state = state.State({})
        current_state = state.State({})

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state.state == {Interface.KEY: []}
        assert current_state.state == {Interface.KEY: []}


class TestDesiredStateBondMetadata(object):
    def test_bond_creation_with_new_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    },
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        current_state = state.State({})
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_BOND

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state.state == expected_dstate.state
        assert current_state == expected_cstate

    def test_bond_creation_with_existing_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces['eth1'] = {'name': 'eth1', 'state': 'up'}
        expected_dstate.interfaces['eth1'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_BOND

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_editing_option(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {'name': BOND_NAME, 'type': TYPE_BOND, 'state': 'down'}
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    },
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_adding_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    },
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        current_state = state.State(
            {Interface.KEY: [{'name': 'eth0', 'type': 'unknown'}]}
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_BOND

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_removing_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0'],
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    },
                    {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND
        expected_dstate.interfaces['eth1'] = {'name': 'eth1'}

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_edit_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {'name': 'eth0', 'type': 'unknown', 'fookey': 'fooval'}
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    },
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_reusing_slave_used_by_existing_bond(self):
        BOND2_NAME = 'bond88'
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND2_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0'],
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': BOND_NAME,
                        'type': TYPE_BOND,
                        'state': 'up',
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth0', 'eth1'],
                        },
                    },
                    {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND2_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate


class TestDesiredStateOvsMetadata(object):
    def test_ovs_creation_with_new_ports(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    },
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        current_state = state.State({})
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][0]
        expected_dstate.interfaces['eth1'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][1]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_creation_with_existing_ports(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'] = {'name': 'eth1', 'state': 'up'}
        expected_dstate.interfaces['eth1'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][0]
        expected_dstate.interfaces['eth1'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][1]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_editing_option(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {'name': OVS_NAME, 'type': TYPE_OVS_BR, 'state': 'down'}
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    },
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_adding_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    },
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {'name': 'eth0', 'state': 'up', 'type': 'unknown'}
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][0]
        expected_dstate.interfaces['eth1'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][1]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_removing_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM}
                            ]
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    },
                    {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'] = {'name': 'eth1'}
        expected_dstate.interfaces['eth0'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]['bridge']['port'][0]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_edit_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {'name': 'eth0', 'type': 'unknown', 'fookey': 'fooval'}
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    },
                    {'name': 'eth0', 'type': 'unknown'},
                    {'name': 'eth1', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][
            metadata.BRPORT_OPTIONS
        ] = current_state.interfaces[OVS_NAME]['bridge']['port'][0]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_reusing_slave_used_by_existing_bridge(self):
        OVS2_NAME = 'ovs-br88'
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS2_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM}
                            ]
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        'name': OVS_NAME,
                        'type': TYPE_OVS_BR,
                        'state': 'up',
                        'bridge': {
                            'port': [
                                {'name': 'eth0', 'type': OBPortType.SYSTEM},
                                {'name': 'eth1', 'type': OBPortType.SYSTEM},
                            ]
                        },
                    },
                    {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                    {'name': 'eth1', 'state': 'up', 'type': 'unknown'},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS2_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS2_NAME]['bridge']['port'][0]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate


class TestRouteMetadata(object):
    def test_with_empty_states(self):
        desired_state = state.State({})
        current_state = state.State({})

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert {} == desired_state.interfaces

    def test_no_routes_with_no_interfaces(self):
        desired_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}}
        )
        current_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: []}}
        )

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert {} == desired_state.interfaces

    def test_route_with_no_desired_or_current_interfaces(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: [route0.to_dict()]}}
        )
        current_state = state.State({})

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert {} == desired_state.interfaces

    def test_route_with_no_desired_or_current_matching_interface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state('foo')],
                Route.KEY: {Route.CONFIG: [route0.to_dict()]},
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state('boo')],
                Route.KEY: {Route.CONFIG: []},
            }
        )

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert 'foo' in desired_state.interfaces
        assert metadata.ROUTES not in desired_state.interfaces['foo']

    def test_route_with_matching_desired_interface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state('eth1')],
                Route.KEY: {Route.CONFIG: [route0.to_dict()]},
            }
        )
        current_state = state.State({})

        metadata.generate_ifaces_metadata(desired_state, current_state)

        iface_state = desired_state.interfaces['eth1']
        route_metadata, = iface_state[Interface.IPV4][metadata.ROUTES]
        assert route0.to_dict() == route_metadata

    def test_route_with_matching_current_interface(self):
        route0 = self._create_route0()
        desired_state = state.State(
            {Interface.KEY: [], Route.KEY: {Route.CONFIG: [route0.to_dict()]}}
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state('eth1')],
                Route.KEY: {Route.CONFIG: []},
            }
        )

        metadata.generate_ifaces_metadata(desired_state, current_state)

        iface_state = desired_state.interfaces['eth1']
        route_metadata, = iface_state[Interface.IPV4][metadata.ROUTES]
        assert route0.to_dict() == route_metadata

    def test_two_routes_with_matching_interfaces(self):
        route0 = self._create_route0()
        route1 = self._create_route1()
        desired_state = state.State(
            {
                Interface.KEY: [_create_interface_state('eth1')],
                Route.KEY: {
                    Route.CONFIG: [route0.to_dict(), route1.to_dict()]
                },
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [_create_interface_state('eth2')],
                Route.KEY: {Route.CONFIG: []},
            }
        )

        metadata.generate_ifaces_metadata(desired_state, current_state)

        iface0_state = desired_state.interfaces['eth1']
        iface1_state = desired_state.interfaces['eth2']
        route0_metadata, = iface0_state[Interface.IPV4][metadata.ROUTES]
        route1_metadata, = iface1_state[Interface.IPV6][metadata.ROUTES]
        assert route0.to_dict() == route0_metadata
        assert route1.to_dict() == route1_metadata

    def _create_route0(self):
        return _create_route('198.51.100.0/24', '192.0.2.1', 'eth1', 50, 103)

    def _create_route1(self):
        return _create_route(
            '2001:db8:a::/64', '2001:db8:1::a', 'eth2', 51, 104
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

    metadata.generate_ifaces_metadata(desired_state, current_state)
    assert (
        nm_dns.DNS_METADATA
        not in desired_state.interfaces[TEST_IFACE1][Interface.IPV4]
    )
    assert (
        nm_dns.DNS_METADATA
        not in desired_state.interfaces[TEST_IFACE1][Interface.IPV6]
    )


def test_dns_gen_metadata_static_gateway_ipv6_name_server_before_ipv4(
    nm_dns_mock
):
    dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888', '8.8.8.8'],
        DNS.SEARCH: ['example.org', 'example.com'],
    }

    desired_state = state.State(
        {
            Interface.KEY: _get_test_iface_states(),
            Route.KEY: {Route.CONFIG: _gen_default_gateway_route(TEST_IFACE1)},
            DNS.KEY: {DNS.CONFIG: dns_config},
        }
    )
    current_state = state.State({})

    metadata.generate_ifaces_metadata(desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: [],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE + 1,
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE,
    }
    iface_state = desired_state.interfaces[TEST_IFACE1]
    assert ipv4_dns_config == iface_state[Interface.IPV4][nm_dns.DNS_METADATA]
    assert ipv6_dns_config == iface_state[Interface.IPV6][nm_dns.DNS_METADATA]


def test_dns_gen_metadata_static_gateway_ipv6_name_server_after_ipv4(
    nm_dns_mock
):
    dns_config = {
        DNS.SERVER: ['8.8.8.8', '2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
    }

    desired_state = state.State(
        {
            Interface.KEY: _get_test_iface_states(),
            Route.KEY: {Route.CONFIG: _gen_default_gateway_route(TEST_IFACE1)},
            DNS.KEY: {DNS.CONFIG: dns_config},
        }
    )
    current_state = state.State({})

    metadata.generate_ifaces_metadata(desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: ['example.org', 'example.com'],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE,
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: [],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE + 1,
    }
    iface_state = desired_state.interfaces[TEST_IFACE1]
    assert ipv4_dns_config == iface_state[Interface.IPV4][nm_dns.DNS_METADATA]
    assert ipv6_dns_config == iface_state[Interface.IPV6][nm_dns.DNS_METADATA]


def test_dns_metadata_interface_not_included_in_desire(nm_dns_mock):
    dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888', '8.8.8.8'],
        DNS.SEARCH: ['example.org', 'example.com'],
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
    metadata.generate_ifaces_metadata(desired_state, current_state)
    iface_state = desired_state.interfaces[TEST_IFACE1]
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: [],
        nm_dns.DNS_METADATA_PRIORITY: nm_dns.DNS_PRIORITY_STATIC_BASE + 1,
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
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
                'address': [{'ip': '192.0.2.251', 'prefix-length': 24}],
                'dhcp': False,
                'enabled': True,
            },
            Interface.IPV6: {
                'address': [{'ip': '2001:db8:1::1', 'prefix-length': 64}],
                'dhcp': False,
                'autoconf': False,
                'enabled': True,
            },
        },
        {
            Interface.NAME: 'eth2',
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                'address': [{'ip': '198.51.100.1', 'prefix-length': 24}],
                'dhcp': False,
                'enabled': True,
            },
            Interface.IPV6: {
                'address': [{'ip': '2001:db8:2::1', 'prefix-length': 64}],
                'dhcp': False,
                'autoconf': False,
                'enabled': True,
            },
        },
    ]


def _gen_default_gateway_route(iface_name):
    return [
        {
            Route.DESTINATION: '0.0.0.0/0',
            Route.METRIC: 200,
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.NEXT_HOP_INTERFACE: iface_name,
            Route.TABLE_ID: 54,
        },
        {
            Route.DESTINATION: '::/0',
            Route.METRIC: 201,
            Route.NEXT_HOP_ADDRESS: '2001:db8:2::f',
            Route.NEXT_HOP_INTERFACE: iface_name,
            Route.TABLE_ID: 54,
        },
    ]
