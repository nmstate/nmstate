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

from libnmstate import metadata
from libnmstate import state
from libnmstate.error import NmstateNotImplementedError
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


class TestDesiredStateMetadata(object):
    def test_empty_states(self):
        desired_state = state.State({})
        current_state = state.State({})

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state.state == {Interface.KEY: []}
        assert current_state.state == {Interface.KEY: []}


class TestDesiredStateBondMetadata(object):
    def test_bond_creation_with_new_slaves(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                },
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
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
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
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
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'down'
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                },
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_adding_slaves(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                },
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
        current_state = state.State({
            Interface.KEY: [{'name': 'eth0', 'type': 'unknown'}]
        })
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
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0']
                    }
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                },
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
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
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': 'eth0',
                    'type': 'unknown',
                    'fookey': 'fooval'
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                },
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = BOND_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_BOND

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_bond_reusing_slave_used_by_existing_bond(self):
        BOND2_NAME = 'bond88'
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND2_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0']
                    }
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': BOND_NAME,
                    'type': TYPE_BOND,
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': ['eth0', 'eth1']
                    }
                },
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
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
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                },
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
        current_state = state.State({})
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][0])
        expected_dstate.interfaces['eth1'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][1])

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_creation_with_existing_ports(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'] = {'name': 'eth1', 'state': 'up'}
        expected_dstate.interfaces['eth1'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][0])
        expected_dstate.interfaces['eth1'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][1])

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_editing_option(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'down'
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                },
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_adding_slaves(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                },
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
        current_state = state.State({
            Interface.KEY: [{'name': 'eth0', 'state': 'up', 'type': 'unknown'}]
        })
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth1'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][0])
        expected_dstate.interfaces['eth1'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][1])

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_removing_slaves(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM}
                        ]
                    }
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                },
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth1'] = {'name': 'eth1'}
        expected_dstate.interfaces['eth0'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS_NAME]['bridge']['port'][0])

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_edit_slave(self):
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': 'eth0',
                    'type': 'unknown',
                    'fookey': 'fooval'
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                },
                {'name': 'eth0', 'type': 'unknown'},
                {'name': 'eth1', 'type': 'unknown'}
            ]
        })
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][metadata.BRPORT_OPTIONS] = (
            current_state.interfaces[OVS_NAME]['bridge']['port'][0])

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_reusing_slave_used_by_existing_bridge(self):
        OVS2_NAME = 'ovs-br88'
        desired_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS2_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM}
                        ]
                    }
                }
            ]
        })
        current_state = state.State({
            Interface.KEY: [
                {
                    'name': OVS_NAME,
                    'type': TYPE_OVS_BR,
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': OBPortType.SYSTEM},
                            {'name': 'eth1', 'type': OBPortType.SYSTEM}
                        ]
                    }
                },
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_dstate.interfaces['eth0'][metadata.MASTER] = OVS2_NAME
        expected_dstate.interfaces['eth0'][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces['eth0'][metadata.BRPORT_OPTIONS] = (
            desired_state.interfaces[OVS2_NAME]['bridge']['port'][0])

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate


def test_route_metadata():
    routes = _get_mixed_test_routes()
    desired_state = state.State({
            Route.KEY: {
                Route.CONFIG: routes,
            },
            Interface.KEY: [
                {
                    Interface.NAME: 'eth1',
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.IPV4: {},
                    Interface.IPV6: {},
                },
                {
                    Interface.NAME: 'eth2',
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.IPV4: {},
                    Interface.IPV6: {},
                },
            ]
    })
    current_state = state.State({})
    metadata.generate_ifaces_metadata(desired_state, current_state)
    expected_iface_state = {
        'eth1': {
            Interface.NAME: 'eth1',
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                metadata.ROUTES: [routes[0]]
            },
            Interface.IPV6: {
                metadata.ROUTES: []
            },
        },
        'eth2': {
            Interface.NAME: 'eth2',
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                metadata.ROUTES: []
            },
            Interface.IPV6: {
                metadata.ROUTES: [routes[1]]
            },
        }
    }
    assert desired_state.interfaces == expected_iface_state


def _get_mixed_test_routes():
    return [
        {
            Route.DESTINATION: '198.51.100.0/24',
            Route.METRIC: 103,
            Route.NEXT_HOP_INTERFACE: 'eth1',
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.TABLE_ID: 50
        },
        {
            Route.DESTINATION: '2001:db8:a::/64',
            Route.METRIC: 104,
            Route.NEXT_HOP_INTERFACE: 'eth2',
            Route.NEXT_HOP_ADDRESS: '2001:db8:1::a',
            Route.TABLE_ID: 51
        }
    ]


def test_dns_metadata_empty():
    desired_state = state.State({
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {},
        DNS.KEY: {}
    })
    current_state = state.State({})

    metadata.generate_ifaces_metadata(desired_state, current_state)
    assert (metadata.DNS_METADATA not in
            desired_state.interfaces['eth1'][Interface.IPV4])
    assert (metadata.DNS_METADATA not in
            desired_state.interfaces['eth1'][Interface.IPV6])


def test_dns_gen_metadata_static_gateway_prefer_ipv6_server():
    dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888', '8.8.8.8'],
        DNS.SEARCH: ['example.org', 'example.com']
    }

    desired_state = state.State({
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {
            Route.CONFIG: _gen_default_gateway_route('eth1')
        },
        DNS.KEY: {
            DNS.CONFIG: dns_config
        }
    })
    current_state = state.State({})

    metadata.generate_ifaces_metadata(desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: [],
        metadata.DNS_METADATA_PRIORITY:
            metadata.DNS_DEFAULT_PRIORITY_FOR_STATIC,
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
        metadata.DNS_METADATA_PRIORITY:
            metadata.DNS_DEFAULT_PRIORITY_FOR_STATIC,
    }
    iface_state = desired_state.interfaces['eth1']
    assert (ipv4_dns_config ==
            iface_state[Interface.IPV4][metadata.DNS_METADATA])
    assert (ipv6_dns_config ==
            iface_state[Interface.IPV6][metadata.DNS_METADATA])


def test_dns_gen_metadata_static_gateway_prefer_ipv4_server():
    dns_config = {
        DNS.SERVER: ['8.8.8.8', '2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com']
    }

    desired_state = state.State({
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {
            Route.CONFIG: _gen_default_gateway_route('eth1')
        },
        DNS.KEY: {
            DNS.CONFIG: dns_config
        }
    })
    current_state = state.State({})

    metadata.generate_ifaces_metadata(desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: [],
        metadata.DNS_METADATA_PRIORITY: metadata.DNS_ORDERING_IPV4_PRIORITY
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
        metadata.DNS_METADATA_PRIORITY: metadata.DNS_ORDERING_IPV6_PRIORITY
    }
    iface_state = desired_state.interfaces['eth1']
    assert (ipv4_dns_config ==
            iface_state[Interface.IPV4][metadata.DNS_METADATA])
    assert (ipv6_dns_config ==
            iface_state[Interface.IPV6][metadata.DNS_METADATA])


def test_dns_gen_metadata_dhcp_no_auto_dns():
    dns_config = {
        DNS.SERVER: ['8.8.8.8', '2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com']
    }

    desired_state = state.State({
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {
            Route.CONFIG: []
        },
        DNS.KEY: {
            DNS.CONFIG: dns_config
        }
    })
    current_state = state.State({})

    metadata.generate_ifaces_metadata(desired_state, current_state)
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: [],
        metadata.DNS_METADATA_PRIORITY: metadata.DNS_ORDERING_IPV4_PRIORITY
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
        metadata.DNS_METADATA_PRIORITY: metadata.DNS_ORDERING_IPV6_PRIORITY
    }
    iface_state = desired_state.interfaces['eth3']
    assert (metadata.DNS_METADATA not in
            desired_state.interfaces['eth1'][Interface.IPV4])
    assert (metadata.DNS_METADATA not in
            desired_state.interfaces['eth1'][Interface.IPV6])
    assert (metadata.DNS_METADATA not in
            desired_state.interfaces['eth2'][Interface.IPV4])
    assert (metadata.DNS_METADATA not in
            desired_state.interfaces['eth2'][Interface.IPV6])
    assert (ipv4_dns_config ==
            iface_state[Interface.IPV4][metadata.DNS_METADATA])
    assert (ipv6_dns_config ==
            iface_state[Interface.IPV6][metadata.DNS_METADATA])


@pytest.mark.xfail(raises=NmstateNotImplementedError,
                   reason='https://nmstate.atlassian.net/browse/NMSTATE-220',
                   strict=True)
def test_dns_gen_metadata_three_servers():
    dns_config = {
        DNS.SERVER: ['8.8.8.8', '2001:4860:4860::8888', '8.8.4.4'],
        DNS.SEARCH: ['example.org', 'example.com']
    }

    desired_state = state.State({
        Interface.KEY: _get_test_iface_states(),
        Route.KEY: {
            Route.CONFIG: []
        },
        DNS.KEY: {
            DNS.CONFIG: dns_config
        }
    })
    current_state = state.State({})
    metadata.generate_ifaces_metadata(desired_state, current_state)


def test_dns_metadata_interface_not_included_in_desire():
    dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888', '8.8.8.8'],
        DNS.SEARCH: ['example.org', 'example.com']
    }

    desired_state = state.State({
        Interface.KEY: [],
        DNS.KEY: {
            DNS.CONFIG: dns_config
        }
    })
    current_state = state.State({
        Interface.KEY: _get_test_iface_states(),
    })
    metadata.generate_ifaces_metadata(desired_state, current_state)
    iface_state = desired_state.interfaces['eth3']
    ipv4_dns_config = {
        DNS.SERVER: ['8.8.8.8'],
        DNS.SEARCH: [],
        metadata.DNS_METADATA_PRIORITY:
            metadata.DNS_DEFAULT_PRIORITY_FOR_STATIC,
    }
    ipv6_dns_config = {
        DNS.SERVER: ['2001:4860:4860::8888'],
        DNS.SEARCH: ['example.org', 'example.com'],
        metadata.DNS_METADATA_PRIORITY:
            metadata.DNS_DEFAULT_PRIORITY_FOR_STATIC,
    }
    assert (ipv4_dns_config ==
            iface_state[Interface.IPV4][metadata.DNS_METADATA])
    assert (ipv6_dns_config ==
            iface_state[Interface.IPV6][metadata.DNS_METADATA])


def _get_test_iface_states():
    return [
        {
            Interface.NAME: 'eth1',
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                'address': [
                    {
                        'ip': '192.0.2.251',
                        'prefix-length': 24
                    }
                ],
                'dhcp': False,
                'enabled': True
            },
            Interface.IPV6: {
                'address': [
                    {
                        'ip': '2001:db8:1::1',
                        'prefix-length': 64
                    }
                ],
                'dhcp': False,
                'autoconf': False,
                'enabled': True
            }
        },
        {
            Interface.NAME: 'eth2',
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                'address': [
                    {
                        'ip': '198.51.100.1',
                        'prefix-length': 24
                    }
                ],
                'dhcp': False,
                'enabled': True
            },
            Interface.IPV6: {
                'address': [
                    {
                        'ip': '2001:db8:2::1',
                        'prefix-length': 64
                    }
                ],
                'dhcp': False,
                'autoconf': False,
                'enabled': True
            }
        },
        {
            Interface.NAME: 'eth3',
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Interface.IPV4: {
                'dhcp': True,
                'auto-dns': False,
                'enabled': True
            },
            Interface.IPV6: {
                'dhcp': True,
                'autoconf': True,
                'auto-dns': False,
                'enabled': True
            }
        }
    ]


def _gen_default_gateway_route(iface_name):
    return [
        {
            Route.DESTINATION: '0.0.0.0/0',
            Route.METRIC: 200,
            Route.NEXT_HOP_ADDRESS: '192.0.2.1',
            Route.NEXT_HOP_INTERFACE: iface_name,
            Route.TABLE_ID: 54
        },
        {
            Route.DESTINATION: '::/0',
            Route.METRIC: 201,
            Route.NEXT_HOP_ADDRESS: '2001:db8:2::f',
            Route.NEXT_HOP_INTERFACE: iface_name,
            Route.TABLE_ID: 54
        }
    ]
