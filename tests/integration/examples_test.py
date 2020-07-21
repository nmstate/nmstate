#
# Copyright (c) 2018-2020 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
""" Test the nmstate example files """
import os

import pytest

from .testlib import assertlib
from .testlib.examplelib import example_state

from libnmstate import netinfo
from libnmstate.error import NmstateNotSupportedError
from libnmstate.schema import DNS


@pytest.mark.tier1
def test_add_down_remove_vlan(eth1_up):
    """
    Test adding, downing and removing a vlan
    """

    vlan_ifname = "eth1.101"
    with example_state(
        "vlan101_eth1_up.yml", cleanup="vlan101_eth1_absent.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)
        with example_state("vlan101_eth1_down.yml") as desired_state:
            assertlib.assert_absent(vlan_ifname)

    assertlib.assert_absent(vlan_ifname)


@pytest.mark.tier1
def test_add_remove_ovs_bridge(eth1_up):
    with example_state(
        "ovsbridge_create.yml", cleanup="ovsbridge_delete.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("ovs-br0")


@pytest.mark.tier1
def test_add_remove_ovs_bridge_bond(eth1_up, eth2_up):
    with example_state(
        "ovsbridge_bond_create.yml", cleanup="ovsbridge_delete.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("ovs-br0")
    assertlib.assert_absent("ovs-bond1")


@pytest.mark.tier1
def test_add_remove_ovs_bridge_vlan(eth1_up, eth2_up):
    with example_state(
        "ovsbridge_vlan_port.yml", cleanup="ovsbridge_delete.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("ovs-br0")


@pytest.mark.tier1
def test_add_remove_linux_bridge(eth1_up):
    with example_state(
        "linuxbrige_eth1_up.yml", cleanup="linuxbrige_eth1_absent.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("linux-br0")


@pytest.mark.tier1
def test_bond_linuxbridge_vlan(eth1_up, eth2_up):
    with example_state(
        "bond_linuxbridge_vlan_up.yml",
        cleanup="bond_linuxbridge_vlan_absent.yml",
    ) as desired_state:
        assertlib.assert_state_match(desired_state)

    assertlib.assert_absent("bond0")
    assertlib.assert_absent("br0")
    assertlib.assert_absent("br29")
    assertlib.assert_absent("vlan29")


@pytest.mark.tier1
def test_dns_edit(eth1_up):
    with example_state(
        "dns_edit_eth1.yml", cleanup="dns_remove.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    current_state = netinfo.show()
    assert current_state.get(DNS.KEY, {}).get(DNS.CONFIG, {}) == {
        DNS.SERVER: [],
        DNS.SEARCH: [],
    }


@pytest.mark.tier1
def test_add_remove_routes(eth1_up):
    """
    Test adding a strict route and removing all routes next hop to eth1.
    """
    with example_state(
        "eth1_add_route.yml", cleanup="eth1_del_all_routes.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_no_config_route_to_iface("eth1")


@pytest.mark.tier1
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Team kmod not available in Travis CI",
)
def test_add_remove_team_with_slaves(eth1_up, eth2_up):
    with example_state(
        "team0_with_slaves.yml", cleanup="team0_absent.yml"
    ) as desired_state:
        assertlib.assert_state_match(desired_state)

    assertlib.assert_absent("team0")


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="SR-IOV device required for this test case",
)
@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_set_ethernet_sriov(eth1_up):
    with example_state("eth1_with_sriov.yml") as desired_state:
        assertlib.assert_state_match(desired_state)


def test_port_vlan(eth1_up):
    with example_state(
        "linuxbrige_eth1_up_port_vlan.yml",
        cleanup="linuxbrige_eth1_absent.yml",
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("linux-br0")


def test_add_ovs_patch_and_remove():
    with example_state(
        "ovsbridge_patch_create.yml", cleanup="ovsbridge_patch_delete.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("patch0")
