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

from contextlib import contextmanager
import pytest
import time
import yaml

from libnmstate import netapplier
from libnmstate import netinfo
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES


MAC0 = '02:ff:ff:ff:ff:00'
MAC1 = '02:ff:ff:ff:ff:01'

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


@contextmanager
def bond_interface(name, slaves):
    desired_state = {
        INTERFACES: [
            {
                'name': name,
                'type': 'bond',
                'state': 'up',
                'link-aggregation': {
                        'mode': 'balance-rr',
                        'slaves': slaves
                }
            }

        ]
    }
    netapplier.apply(desired_state)
    try:
        yield desired_state
    finally:
        netapplier.apply({
                INTERFACES: [
                    {
                        'name': name,
                        'type': 'bond',
                        'state': 'absent'
                    }
                ]
            }
        )


def test_add_and_remove_bond_with_two_slaves(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE, Loader=yaml.SafeLoader)
    netapplier.apply(state)

    assertlib.assert_state(state)

    state[INTERFACES][0]['state'] = 'absent'

    netapplier.apply(state)

    state = statelib.show_only((state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_remove_bond_with_minimum_desired_state(eth1_up, eth2_up):
    state = yaml.load(BOND99_YAML_BASE, Loader=yaml.SafeLoader)
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
    with bond_interface(name='bond99', slaves=[]) as bond_state:

        assert bond_state[INTERFACES][0]['link-aggregation']['slaves'] == []


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


def test_rollback_for_bond(eth1_up, eth2_up):
    current_state = netinfo.show()
    desired_state = {
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

    desired_state[INTERFACES][0]['invalid_key'] = 'foo'

    with pytest.raises(NmstateVerificationError):
        netapplier.apply(desired_state)

    time.sleep(5)

    current_state_after_apply = netinfo.show()
    assert current_state[INTERFACES] == current_state_after_apply[INTERFACES]


def test_add_slave_to_bond_without_slaves(eth1_up):

    with bond_interface(name='bond99', slaves=[]) as bond_state:

        bond_state[INTERFACES][0]['link-aggregation']['slaves'] = ['eth1']
        netapplier.apply(bond_state)

        current_state = statelib.show_only(('bond99',))
        bond99_cur_state = current_state[INTERFACES][0]

        assert bond99_cur_state['link-aggregation']['slaves'][0] == 'eth1'


@pytest.mark.xfail(strict=True, reason="Jira issue # NMSTATE-143")
def test_remove_all_slaves_from_bond(eth1_up):

    with bond_interface(name='bond99', slaves=['eth1']) as bond_state:
        bond_state[INTERFACES][0]['link-aggregation']['slaves'] = []

        netapplier.apply(bond_state)

        current_state = statelib.show_only(('bond99',))
        bond99_cur_state = current_state[INTERFACES][0]

        assert bond99_cur_state['link-aggregation']['slaves'] == []


def test_replace_bond_slave(eth1_up, eth2_up):

    with bond_interface(name='bond99', slaves=['eth1']) as bond_state:
        bond_state[INTERFACES][0]['link-aggregation']['slaves'] = ['eth2']

        netapplier.apply(bond_state)

        current_state = statelib.show_only(('bond99',))
        bond99_cur_state = current_state[INTERFACES][0]

        assert bond99_cur_state['link-aggregation']['slaves'][0] == 'eth2'


def test_remove_one_of_the_bond_slaves(eth1_up, eth2_up):
    with bond_interface(name='bond99', slaves=['eth1', 'eth2']) as bond_state:

        bond_state[INTERFACES][0]['link-aggregation']['slaves'] = ['eth2']

        netapplier.apply(bond_state)

        current_state = statelib.show_only(('bond99',))
        bond99_cur_state = current_state[INTERFACES][0]

    assert bond99_cur_state['link-aggregation']['slaves'] == ['eth2']


def test_set_bond_mac_address(eth1_up):
    with bond_interface(name='bond99', slaves=['eth1']) as bond_state:
        bond_state[Interface.KEY][0][Interface.MAC] = MAC0
        netapplier.apply(bond_state)

        current_state = statelib.show_only(('bond99',))
        bond99_cur_state = current_state[INTERFACES][0]
        assert bond99_cur_state[Interface.MAC] == MAC0.upper()

        bond_state[Interface.KEY][0][Interface.MAC] = MAC1
        netapplier.apply(bond_state)

        current_state = statelib.show_only(('bond99',))
        bond99_cur_state = current_state[INTERFACES][0]
        assert bond99_cur_state[Interface.MAC] == MAC1.upper()
