#
# Copyright 2018-2019 Red Hat, Inc.
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

import libnmstate
from libnmstate import schema
from libnmstate import state
from libnmstate.schema import DNS
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError


class TestLinkAggregationState(object):
    def test_bonds_with_no_slaves(self):
        desired_state = state.State({
            schema.Interface.KEY: [
                {
                    'name': 'bond0',
                    'link-aggregation': {
                        'slaves': []
                    },
                },
                {
                    'name': 'bond1',
                    'link-aggregation': {
                        'slaves': []
                    },
                }
            ]
        })

        libnmstate.validator.validate_link_aggregation_state(desired_state,
                                                             empty_state())

    def test_bonds_with_single_slave(self):
        desired_state = state.State({
            schema.Interface.KEY: [
                {'name': 'slave0'},
                {'name': 'slave1'},
                {
                    'name': 'bond0',
                    'link-aggregation': {
                        'slaves': ['slave0']
                    },
                },
                {
                    'name': 'bond1',
                    'link-aggregation': {
                        'slaves': ['slave1']
                    },
                }
            ]
        })
        libnmstate.validator.validate_link_aggregation_state(desired_state,
                                                             empty_state())

    def test_bonds_with_multiple_slaves(self):
        desired_state = state.State({
            schema.Interface.KEY: [
                {'name': 'slave0'},
                {'name': 'slave1'},
                {'name': 'slave00'},
                {'name': 'slave11'},
                {
                    'name': 'bond0',
                    'link-aggregation': {
                        'slaves': ['slave0', 'slave00']
                    },
                },
                {
                    'name': 'bond1',
                    'link-aggregation': {
                        'slaves': ['slave1', 'slave11']
                    },
                }
            ]
        })
        libnmstate.validator.validate_link_aggregation_state(desired_state,
                                                             empty_state())

    def test_bonds_with_multiple_slaves_reused(self):
        desired_state = state.State({
            schema.Interface.KEY: [
                {'name': 'slave0'},
                {'name': 'slave1'},
                {'name': 'slave00'},
                {
                    'name': 'bond0',
                    'link-aggregation': {
                        'slaves': ['slave0', 'slave00']
                    },
                },
                {
                    'name': 'bond1',
                    'link-aggregation': {
                        'slaves': ['slave1', 'slave00']
                    },
                }
            ]
        })
        with pytest.raises(NmstateValueError):
            libnmstate.validator.validate_link_aggregation_state(desired_state,
                                                                 empty_state())

    def test_bonds_with_missing_slaves(self):
        desired_state = state.State({
            schema.Interface.KEY: [
                {'name': 'slave0'},
                {'name': 'slave1'},
                {
                    'name': 'bond0',
                    'link-aggregation': {
                        'slaves': ['slave0', 'slave00']
                    },
                },
                {
                    'name': 'bond1',
                    'link-aggregation': {
                        'slaves': ['slave1', 'slave11']
                    },
                }
            ]
        })
        with pytest.raises(NmstateValueError):
            libnmstate.validator.validate_link_aggregation_state(desired_state,
                                                                 empty_state())


@pytest.mark.xfail(raises=NmstateNotImplementedError,
                   reason='https://nmstate.atlassian.net/browse/NMSTATE-220',
                   strict=True)
def test_dns_three_nameservers():
    libnmstate.validator.validate_dns({
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: ['8.8.8.8', '2001:4860:4860::8888', '8.8.4.4']
            }
        }
    })


def empty_state():
    return state.State({})
