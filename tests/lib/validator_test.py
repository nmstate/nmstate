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

import pytest

import libnmstate


class TestLinkAggregationState(object):
    def test_bonds_with_no_slaves(self):
        config = [
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
        libnmstate.validator.verify_link_aggregation_state(config, {})

    def test_bonds_with_single_slave(self):
        config = [
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
        libnmstate.validator.verify_link_aggregation_state(config, {})

    def test_bonds_with_multiple_slaves(self):
        config = [
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
        libnmstate.validator.verify_link_aggregation_state(config, {})

    def test_bonds_with_multiple_slaves_reused(self):
        config = [
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
        with pytest.raises(
                libnmstate.validator.LinkAggregationSlavesReuseError):
            libnmstate.validator.verify_link_aggregation_state(config, {})

    def test_bonds_with_missing_slaves(self):
        config = [
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
        with pytest.raises(
                libnmstate.validator.LinkAggregationSlavesMissingError):
            libnmstate.validator.verify_link_aggregation_state(config, {})
