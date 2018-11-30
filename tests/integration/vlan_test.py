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
import os.path

import yaml

from libnmstate import netapplier

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES


VLAN_IFNAME = 'eth1.101'
VLAN2_IFNAME = 'eth1.102'

PATH_MAX = 4096


def test_add_and_remove_vlan(eth1_up):
    with vlan_interface(VLAN_IFNAME, 101) as desired_state:
        assertlib.assert_state(desired_state)

    current_state = statelib.show_only((VLAN_IFNAME,))
    assert not current_state[INTERFACES]


def test_add_and_remove_two_vlans_on_same_iface(eth1_up):
    with two_vlans_on_eth1() as desired_state:
        assertlib.assert_state(desired_state)

    vlan_interfaces = [i['name'] for i in desired_state[INTERFACES]]
    current_state = statelib.show_only(vlan_interfaces)
    assert not current_state[INTERFACES]


def test_set_vlan_iface_down(eth1_up):
    with vlan_interface(VLAN_IFNAME, 101):
        netapplier.apply({
                INTERFACES: [
                    {
                        'name': VLAN_IFNAME,
                        'type': 'vlan',
                        'state': 'down'
                    }
                ]
            }
        )

        current_state = statelib.show_only((VLAN_IFNAME,))
        assert not current_state[INTERFACES]


def test_add_down_remove_vlan(eth1_up):
    with yaml_state('vlan101_eth1_up.yml',
                    cleanup='vlan101_eth1_absent.yml') as desired_state:
        assertlib.assert_state(desired_state)
        with yaml_state('vlan101_eth1_down.yml') as desired_state:
            assertlib.assert_absent(VLAN_IFNAME)

    assertlib.assert_absent(VLAN_IFNAME)


@contextmanager
def yaml_state(initial, cleanup=None):
    desired_state = load_example(initial)

    netapplier.apply(desired_state)
    try:
        yield desired_state
    finally:
        if cleanup:
            netapplier.apply(load_example(cleanup))


def load_example(name):
    examples = find_examples_dir()

    with open(os.path.join(examples, name)) as yamlfile:
        state = yaml.load(yamlfile)

    return state


def find_examples_dir():
    path = ''
    parent = '../'
    rootdir = '/'
    examples = None
    for _ in range(PATH_MAX / len('x/')):
        maybe_examples = os.path.abspath(os.path.join(path, 'examples'))
        if os.path.isdir(maybe_examples):
            examples = maybe_examples
            break

        if os.path.abspath(path) == rootdir:
            break

        path = parent + path

    if examples:
        return examples
    else:
        raise RuntimeError('Cannot find examples directory')


@contextmanager
def vlan_interface(ifname, vlan_id):
    desired_state = {
        INTERFACES: [
            {
                'name': ifname,
                'type': 'vlan',
                'state': 'up',
                'vlan': {
                    'id': vlan_id,
                    'base-iface': 'eth1'
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
                        'name': ifname,
                        'type': 'vlan',
                        'state': 'absent'
                    }
                ]
            }
        )


@contextmanager
def two_vlans_on_eth1():
    desired_state = {
        INTERFACES: [
            {
                'name': VLAN_IFNAME,
                'type': 'vlan',
                'state': 'up',
                'vlan': {
                        'id': 101,
                        'base-iface': 'eth1'
                }
            },
            {

                'name': VLAN2_IFNAME,
                'type': 'vlan',
                'state': 'up',
                'vlan': {
                        'id': 102,
                        'base-iface': 'eth1'
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
                        'name': VLAN_IFNAME,
                        'type': 'vlan',
                        'state': 'absent'
                    },
                    {
                        'name': VLAN2_IFNAME,
                        'type': 'vlan',
                        'state': 'absent'
                    }

                ]
            }
        )
