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
""" Test the nmstate example files """

from contextlib import contextmanager
import os.path

import yaml

from libnmstate import netapplier

from .testlib import assertlib

PATH_MAX = 4096


def test_add_down_remove_vlan(eth1_up):
    """
    Test adding, downing and removing a vlan
    """

    vlan_ifname = 'eth1.101'
    with yaml_state('vlan101_eth1_up.yml',
                    cleanup='vlan101_eth1_absent.yml') as desired_state:
        assertlib.assert_state(desired_state)
        with yaml_state('vlan101_eth1_down.yml') as desired_state:
            assertlib.assert_absent(vlan_ifname)

    assertlib.assert_absent(vlan_ifname)


@contextmanager
def yaml_state(initial, cleanup=None):
    """
    Apply the initial state and optionally the cleanup state at the end
    """

    desired_state = load_example(initial)

    netapplier.apply(desired_state)
    try:
        yield desired_state
    finally:
        if cleanup:
            netapplier.apply(load_example(cleanup))


def load_example(name):
    """
    Load the state from an example yaml file
    """

    examples = find_examples_dir()

    with open(os.path.join(examples, name)) as yamlfile:
        state = yaml.load(yamlfile)

    return state


def find_examples_dir():
    """
    Look recursively for the directory containing the examples
    """

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
