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

from libnmstate import state
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface


class TestAssertIfaceState(object):

    def test_desired_is_identical_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state

        desired_state.verify_interfaces(current_state)

    def test_desired_is_partial_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state
        extra_state = self._extra_state
        current_state.interfaces.update(extra_state.interfaces)

        desired_state.verify_interfaces(current_state)

    def test_current_is_partial_to_desired(self):
        desired_state = self._base_state
        current_state = self._base_state
        extra_state = self._extra_state
        desired_state.interfaces.update(extra_state.interfaces)

        with pytest.raises(NmstateVerificationError):
            desired_state.verify_interfaces(current_state)

    def test_desired_is_not_equal_to_current(self):
        desired_state = self._base_state
        current_state = self._base_state
        current_state.interfaces['foo-name']['state'] = 'down'

        with pytest.raises(NmstateVerificationError):
            desired_state.verify_interfaces(current_state)

    def test_sort_multiple_ip(self):
        desired_state = self._base_state
        current_state = self._base_state
        desired_state.interfaces['foo-name']['ipv4'] = {
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
        current_state.interfaces['foo-name']['ipv4'] = {
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
        desired_state.interfaces['foo-name']['ipv6'] = {
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
        current_state.interfaces['foo-name']['ipv6'] = {
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

        desired_state.verify_interfaces(current_state)

    @property
    def _base_state(self):
        return state.State({
            Interface.KEY: [
                {
                    'name': 'foo-name',
                    'type': 'foo-type',
                    'state': 'up',
                    'bridge': {
                        'port': [
                            {'name': 'eth0', 'type': 'system'}
                        ]
                    }
                }
            ]
        })

    @property
    def _extra_state(self):
        return state.State({
            Interface.KEY: [
                {'name': 'eth0', 'state': 'up', 'type': 'unknown'},
                {'name': 'eth1', 'state': 'up', 'type': 'unknown'}
            ]
        })
