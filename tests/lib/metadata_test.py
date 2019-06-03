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

from libnmstate import metadata
from libnmstate import state
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
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
