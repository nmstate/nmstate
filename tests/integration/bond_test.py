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
import yaml

from libnmstate import netapplier

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES


BOND99_YAML_BASE = """
interfaces:
- name: bond99
  type: bond
  state: up
  link-aggregation:
    mode: balance-rr
    slaves:
    - eth1
    - eth2
"""


@pytest.fixture
def setup_remove_bond99():
    yield
    remove_bond = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': 'bond',
                'state': 'absent'
            }
        ]
    }
    netapplier.apply(remove_bond)


def test_add_and_remove_bond_with_two_slaves(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE)
    netapplier.apply(state)

    assertlib.assert_state(state)

    state[INTERFACES][0]['state'] = 'absent'

    netapplier.apply(state)

    state = statelib.show_only((state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_remove_bond_with_minimum_desired_state(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE)
    netapplier.apply(state)

    remove_bond_state = {
        INTERFACES: [
            {
                'name': 'bond99',
                'type': 'bond',
                'state': 'absent'
            }
        ]
    }
    netapplier.apply(remove_bond_state)
    state = statelib.show_only((state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_add_bond_without_slaves():
    desired_bond_state = {
            INTERFACES: [
                {
                    'name': 'bond99',
                    'type': 'bond',
                    'state': 'up',
                    'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': []
                    },
                }

            ]
        }

    netapplier.apply(desired_bond_state)

    assertlib.assert_state(desired_bond_state)


def test_add_bond_with_slaves_and_ipv4(eth1_up, eth2_up, setup_remove_bond99):
    desired_bond_state = {
                INTERFACES: [
                    {
                        'name': 'bond99',
                        'type': 'bond',
                        'state': 'up',
                        'ipv4': {
                            'enabled': True,
                            'address': [
                                {'ip': '192.168.122.250', 'prefix-length': 24}
                            ]
                        },
                        'link-aggregation': {
                            'mode': 'balance-rr',
                            'slaves': ['eth1', 'eth2'],
                            'options':
                                {'miimon': '140'}
                        },
                    }
                ]
            }

    netapplier.apply(desired_bond_state)

    assertlib.assert_state(desired_bond_state)
