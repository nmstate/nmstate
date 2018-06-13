#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

import copy

import pytest

from .compat import mock

from libnmstate import netapplier


UP = 1
DOWN = 0

BOND_NAME = 'bond99'


@pytest.fixture()
def config():
    return {'interfaces': create_config()}


def create_config():
    return [
        {'name': 'foo', 'type': 'unknown', 'state': 'up'}
    ]


@mock.patch('libnmstate.netapplier.netinfo.interfaces', create_config)
@mock.patch('libnmstate.nmclient.NM')
@mock.patch('libnmstate.nmclient.client')
class TestDevStateChange(object):
    def test_apply_iface_state_up_to_up(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=UP)
        mk_nm.DeviceState.ACTIVATED = UP

        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_called_once()
        mk_client.return_value.deactivate_connection_async.assert_not_called()

    def test_apply_iface_state_down_to_up(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=DOWN)
        mk_nm.DeviceState.ACTIVATED = UP

        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_called_once()
        mk_client.return_value.deactivate_connection_async.assert_not_called()

    def test_apply_iface_state_down_to_down(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(
            devstate=DOWN, active_connection=None)
        mk_nm.DeviceState.ACTIVATED = UP

        config['interfaces'][0]['state'] = 'down'
        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_not_called()
        mk_client.return_value.deactivate_connection_async.assert_not_called()

    def test_apply_iface_state_up_to_down(self, mk_client, mk_nm, config):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=UP)
        mk_nm.DeviceState.ACTIVATED = UP

        config['interfaces'][0]['state'] = 'down'
        netapplier.apply(config)

        mk_client.return_value.activate_connection_async.assert_not_called()
        mk_client.return_value.deactivate_connection_async.assert_called_once()


@mock.patch('libnmstate.netapplier.netinfo.interfaces', create_config)
@mock.patch('libnmstate.nmclient.NM')
@mock.patch('libnmstate.nmclient.client')
class TestBond(object):
    def test_apply_new_bond(self, mk_client, mk_nm):
        mock_get_device_by_iface = mk_client.return_value.get_device_by_iface
        mock_get_device_by_iface.return_value = MockNmDevice(devstate=UP)
        mk_nm.DeviceState.ACTIVATED = UP
        mk_nm.SETTING_BOND_SETTING_NAME = 'bond'

        new_bond_config = {
            'interfaces': [
                {
                    'name': 'bond99',
                    'type': 'bond',
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'options': {
                            'miimon': 120
                        }
                    }
                 }
            ]
        }
        netapplier.apply(new_bond_config)

        mk_client.return_value.add_connection_async.assert_called_once()


class TestDesiredStateMetadata(object):
    def test_empty_states(self):
        desired_state = {}
        current_state = {}

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == {}
        assert current_state == {}

    def test_bond_creation_with_new_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'type': 'unknown'},
            'eth1': {'type': 'unknown'}
        }
        current_state = {}
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth1']['_master'] = BOND_NAME

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_creation_with_existing_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            }
        }
        current_state = {
            'eth0': {'type': 'unknown'},
            'eth1': {'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {}
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth1'] = {}
        expected_desired_state['eth1']['_master'] = BOND_NAME

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_editing_option(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': 'bond',
                'state': 'down'
            }
        }
        current_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'type': 'unknown'},
            'eth1': {'type': 'unknown'}
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
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth1': {'type': 'unknown'}
        }
        current_state = {
            'eth0': {'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {}
        expected_desired_state['eth0']['_master'] = BOND_NAME
        expected_desired_state['eth1']['_master'] = BOND_NAME

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_bond_removing_slaves(self):
        desired_state = {
            BOND_NAME: {
                'name': BOND_NAME,
                'type': 'bond',
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
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'type': 'unknown'},
            'eth1': {'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0'] = {}
        expected_desired_state['eth0']['_master'] = BOND_NAME
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
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                    'mode': 'balance-rr',
                    'slaves': ['eth0', 'eth1']
                }
            },
            'eth0': {'type': 'unknown'},
            'eth1': {'type': 'unknown'}
        }
        expected_desired_state = copy.deepcopy(desired_state)
        expected_current_state = copy.deepcopy(current_state)
        expected_desired_state['eth0']['_master'] = BOND_NAME

        netapplier.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state


class MockNmDevice(object):

    def __init__(self, devstate, active_connection=mock.MagicMock()):
        self._state = devstate
        self._active_connection = active_connection

    def get_active_connection(self):
        return self._active_connection

    def get_state(self):
        return self._state
