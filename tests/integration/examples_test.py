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
""" Test the nmstate example files """

from .testlib import assertlib
from .testlib.examplelib import example_state


def test_add_down_remove_vlan(eth1_up):
    """
    Test adding, downing and removing a vlan
    """

    vlan_ifname = 'eth1.101'
    with example_state('vlan101_eth1_up.yml',
                       cleanup='vlan101_eth1_absent.yml') as desired_state:
        assertlib.assert_state(desired_state)
        with example_state('vlan101_eth1_down.yml') as desired_state:
            assertlib.assert_absent(vlan_ifname)

    assertlib.assert_absent(vlan_ifname)


def test_add_remove_ovs_bridge(eth1_up):
    with example_state('ovsbridge_create.yml',
                       cleanup='ovsbridge_delete.yml') as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent('ovs-br0')


def test_add_remove_linux_bridge(eth1_up):
    with example_state('linuxbrige_eth1_up.yml',
                       cleanup='linuxbrige_eth1_absent.yml') as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent('linux-br0')
