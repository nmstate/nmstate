#
# Copyright 2018 Red Hat, Inc.
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
import copy

import pytest

from .compat import mock

from libnmstate import netapplier
from libnmstate.schema import Constants


INTERFACES = Constants.INTERFACES
BOND_TYPE = 'bond'
OVS_BR_TYPE = 'ovs-bridge'
BOND_NAME = 'bond99'
OVS_NAME = 'ovs-br99'


@pytest.fixture(scope='module', autouse=True)
def nmclient_mock():
    client_mock = mock.patch.object(netapplier.nmclient, 'client')
    mainloop_mock = mock.patch.object(netapplier.nmclient, 'mainloop')
    with client_mock, mainloop_mock:
        yield


@pytest.fixture
def netapplier_nm_mock():
    with mock.patch.object(netapplier, 'nm') as m:
        m.applier.prepare_proxy_ifaces_desired_state.return_value = []
        yield m


@pytest.fixture
def netinfo_nm_mock():
    with mock.patch.object(netapplier.netinfo, 'nm') as m:
        yield m


def test_iface_admin_state_change(netinfo_nm_mock, netapplier_nm_mock):
    current_config = {
        INTERFACES: [
            {
                'name': 'foo',
                'type': 'unknown',
                'state': 'up',
                'ipv4': {
                    'enabled': False,
                },
                'ipv6': {
                    'enabled': False,
                },
            }
        ]
    }
    desired_config = copy.deepcopy(current_config)

    netinfo_nm_mock.device.list_devices.return_value = ['one-item']
    netinfo_nm_mock.translator.Nm2Api.get_common_device_info.return_value = (
        current_config[INTERFACES][0])
    netinfo_nm_mock.bond.is_bond_type_id.return_value = False
    netinfo_nm_mock.ovs.is_ovs_bridge_type_id.return_value = False
    netinfo_nm_mock.ovs.is_ovs_port_type_id.return_value = False
    netinfo_nm_mock.ipv4.get_info.return_value = (
        current_config[INTERFACES][0]['ipv4'])
    netinfo_nm_mock.ipv6.get_info.return_value = (
        current_config[INTERFACES][0]['ipv6'])

    desired_config[INTERFACES][0]['state'] = 'down'
    netapplier.apply(desired_config, verify_change=False)

    applier_mock = netapplier_nm_mock.applier
    ifaces_conf = applier_mock.prepare_new_ifaces_configuration.return_value
    applier_mock.set_ifaces_admin_state.assert_has_calls(
        [
            mock.call([], con_profiles=ifaces_conf),
            mock.call(desired_config[INTERFACES])
        ]
    )


def test_add_new_bond(netinfo_nm_mock, netapplier_nm_mock):
    netinfo_nm_mock.device.list_devices.return_value = []

    desired_config = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': [],
                    'options': {
                        'miimon': 200,
                    }
                }
            }
        ]
    }

    netapplier.apply(desired_config, verify_change=False)

    m_prepare = netapplier_nm_mock.applier.prepare_edited_ifaces_configuration
    m_prepare.assert_called_once_with([])

    m_prepare = netapplier_nm_mock.applier.prepare_new_ifaces_configuration
    m_prepare.assert_called_once_with(desired_config[INTERFACES])


def test_edit_existing_bond(netinfo_nm_mock, netapplier_nm_mock):
    current_config = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': [],
                    'options': {
                        'miimon': '100',
                    }
                },
                'ipv4': {
                    'enabled': False,
                },
                'ipv6': {
                    'enabled': False,
                },
            }
        ]
    }

    netinfo_nm_mock.device.list_devices.return_value = ['one-item']
    netinfo_nm_mock.translator.Nm2Api.get_common_device_info.return_value = {
        'name': current_config[INTERFACES][0]['name'],
        'type': current_config[INTERFACES][0]['type'],
        'state': current_config[INTERFACES][0]['state'],
    }
    netinfo_nm_mock.bond.is_bond_type_id.return_value = True
    netinfo_nm_mock.translator.Nm2Api.get_bond_info.return_value = {
        'link-aggregation': current_config[INTERFACES][0]['link-aggregation']
    }
    netinfo_nm_mock.ipv4.get_info.return_value = (
        current_config[INTERFACES][0]['ipv4'])
    netinfo_nm_mock.ipv6.get_info.return_value = (
        current_config[INTERFACES][0]['ipv6'])

    desired_config = copy.deepcopy(current_config)
    options = desired_config[INTERFACES][0]['link-aggregation']['options']
    options['miimon'] = 200

    netapplier.apply(desired_config, verify_change=False)

    m_prepare = netapplier_nm_mock.applier.prepare_edited_ifaces_configuration
    m_prepare.assert_called_once_with(desired_config[INTERFACES])

    m_prepare = netapplier_nm_mock.applier.prepare_new_ifaces_configuration
    m_prepare.assert_called_once_with([])


class TestDesiredStateMetadata(object):
    def test_empty_states(self):
        desired_state = {}
        current_state = {}

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == {}
        assert current_state == {}


class TestDesiredStateBondMetadata(object):
    def test_bond_creation_with_new_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        current_state = {}
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth1']['_master'] = BOND_NAME
        expected_desired_state['eth0']['_master_type'] = BOND_TYPE
        expected_desired_state['eth1']['_master_type'] = BOND_TYPE

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_creation_with_existing_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            }
        }
        current_state = {
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth0']['_master_type'] = BOND_TYPE
        expected_desired_state['eth1'] = {'name': 'eth1', 'state': 'up'}
        expected_desired_state['eth1']['_master'] = BOND_NAME
        expected_desired_state['eth1']['_master_type'] = BOND_TYPE

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_editing_option(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'down'
            }
        }
        current_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_adding_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        current_state = {
            'eth0': {'name': 'eth0', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth1']['_master'] = BOND_NAME
        expected_desired_state['eth0']['_master_type'] = BOND_TYPE
        expected_desired_state['eth1']['_master_type'] = BOND_TYPE

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_removing_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0']
                }
            }
        }
        current_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth0']['_master_type'] = BOND_TYPE
        expected_desired_state['eth1'] = {}

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_edit_slave(self):
        desired_state = {
            'eth0': {
                'name': 'eth0',
                'type': 'unknown',
                'fookey': 'fooval'
            }
        }
        current_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth0']['_master_type'] = BOND_TYPE

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_reusing_slave_used_by_existing_bond(self):
        BOND2_NAME = 'bond88'
        desired_state = {
            BOND2_NAME: {
                'name': BOND2_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0']
                }
            }
        }
        current_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': BOND_TYPE,
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = BOND2_NAME
        expected_desired_state['eth0']['_master_type'] = BOND_TYPE

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state


class TestDesiredStateOvsMetadata(object):
    def test_ovs_creation_with_new_ports(self):
        desired_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            },
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        current_state = {}
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0']['_master'] = OVS_NAME
        expected_desired_state['eth1']['_master'] = OVS_NAME
        expected_desired_state['eth0']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth1']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth0']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][0])
        expected_desired_state['eth1']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][1])

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_creation_with_existing_ports(self):
        desired_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            }
        }
        current_state = {
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = OVS_NAME
        expected_desired_state['eth0']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth1'] = {'name': 'eth1', 'state': 'up'}
        expected_desired_state['eth1']['_master'] = OVS_NAME
        expected_desired_state['eth1']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth0']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][0])
        expected_desired_state['eth1']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][1])

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_editing_option(self):
        desired_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'down'
            }
        }
        current_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            },
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_adding_slaves(self):
        desired_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            },
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        current_state = {
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = OVS_NAME
        expected_desired_state['eth1']['_master'] = OVS_NAME
        expected_desired_state['eth0']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth1']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth0']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][0])
        expected_desired_state['eth1']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][1])

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_removing_slaves(self):
        desired_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'}
                    ]
                }
            }
        }
        current_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            },
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = OVS_NAME
        expected_desired_state['eth0']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth1'] = {}
        expected_desired_state['eth0']['_brport_options'] = (
            desired_state[OVS_NAME]['bridge']['port'][0])

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_edit_slave(self):
        desired_state = {
            'eth0': {
                'name': 'eth0',
                'type': 'unknown',
                'fookey': 'fooval'
            }
        }
        current_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            },
            'eth0': {'name': 'eth0', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0']['_master'] = OVS_NAME
        expected_desired_state['eth0']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth0']['_brport_options'] = (
            current_state[OVS_NAME]['bridge']['port'][0])

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_reusing_slave_used_by_existing_bridge(self):
        OVS2_NAME = 'ovs-br88'
        desired_state = {
            OVS2_NAME: {
                'name': OVS2_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'}
                    ]
                }
            }
        }
        current_state = {
            OVS_NAME: {
                'name': OVS_NAME,
                'type': OVS_BR_TYPE,
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'},
                        {'name': 'eth1', 'type': 'system'}
                    ]
                }
            },
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {'name': 'eth0', 'state': 'up'}
        expected_desired_state['eth0']['_master'] = OVS2_NAME
        expected_desired_state['eth0']['_master_type'] = OVS_BR_TYPE
        expected_desired_state['eth0']['_brport_options'] = (
            desired_state[OVS2_NAME]['bridge']['port'][0])

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state


class TestAssertIfaceState(object):

    def test_desired_is_identical_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state

        netapplier.assert_ifaces_state(desired_state, current_state)

    def test_desired_is_partial_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state
        current_state.update({
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        })

        netapplier.assert_ifaces_state(desired_state, current_state)

    def test_current_is_partial_to_desired(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state.update({
            'eth0': {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
            'eth1': {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
        })

        with pytest.raises(netapplier.DesiredStateIsNotCurrentError):
            netapplier.assert_ifaces_state(desired_state, current_state)

    def test_desired_is_not_equal_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state
        current_state['foo-name']['state'] = 'down'

        with pytest.raises(netapplier.DesiredStateIsNotCurrentError):
            netapplier.assert_ifaces_state(desired_state, current_state)

    def test_sort_multiple_ip(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state['foo-name']['ipv4'] = {
            'address': [
                {
                    'ip': '192.168.122.10',
                    'prefix-length': 24
                },
                {
                    'ip': '192.168.121.10',
                    'prefix-length': 24
                },
            ],
            'enabled': True
        }
        current_state['foo-name']['ipv4'] = {
            'address': [
                {
                    'ip': '192.168.121.10',
                    'prefix-length': 24
                },
                {
                    'ip': '192.168.122.10',
                    'prefix-length': 24
                },
            ],
            'enabled': True
        }
        desired_state['foo-name']['ipv6'] = {
            'address': [
                {
                    'ip': '2001::2',
                    'prefix-length': 64
                },
                {
                    'ip': '2001::1',
                    'prefix-length': 64
                }
            ],
            'enabled': True
        }
        current_state['foo-name']['ipv6'] = {
            'address': [
                {
                    'ip': '2001::1',
                    'prefix-length': 64
                },
                {
                    'ip': '2001::2',
                    'prefix-length': 64
                }
            ],
            'enabled': True
        }

        netapplier.assert_ifaces_state(desired_state, current_state)

    @property
    def _base_state(self):
        return {
            'foo-name': {
                'name': 'foo-name',
                'type': 'foo-type',
                'state': 'up',
                'bridge': {
                    'port': [
                        {'name': 'eth0', 'type': 'system'}
                    ]
                }
            }
        }
