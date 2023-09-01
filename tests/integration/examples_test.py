#
# Copyright (c) 2018-2021 Red Hat, Inc.
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
from .testlib import iprule
from .testlib.examplelib import example_state
from .testlib.examplelib import find_examples_dir
from .testlib.examplelib import load_example

import libnmstate
from libnmstate import netinfo
from libnmstate.error import NmstateNotSupportedError
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import DNS
from libnmstate.schema import HostNameState
from libnmstate.schema import RouteRule

from .testlib.env import is_k8s
from .testlib.env import nm_major_minor_version


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
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=NmstateVerificationError,
    strict=False,
)
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
        assertlib.assert_state_match(desired_state)

    assertlib.assert_absent("ovs-br0")
    assertlib.assert_absent("ovs-bond1")


@pytest.mark.tier1
def test_add_remove_ovs_bridge_vlan(eth1_up, eth2_up):
    with example_state(
        "ovsbridge_vlan_port.yml", cleanup="ovsbridge_delete.yml"
    ) as desired_state:
        assertlib.assert_state_match(desired_state)

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
        assertlib.assert_state_match(desired_state)

    current_state = netinfo.show()
    assert current_state.get(DNS.KEY, {}).get(DNS.CONFIG, {}) == {}


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
def test_add_remove_route_rule(eth1_up):
    """
    Test adding a route rule and removing all route rules next hop to eth1.
    """
    with example_state(
        "eth1_add_route_rule.yml", cleanup="eth1_del_all_route_rules.yml"
    ) as desired_state:
        for rule in desired_state[RouteRule.KEY][RouteRule.CONFIG]:
            iprule.ip_rule_exist_in_os(rule)


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


def test_add_remove_vrf(eth1_up):
    with example_state(
        "vrf0_with_eth1.yml", cleanup="vrf0_absent.yml"
    ) as desired_state:
        assertlib.assert_state_match(desired_state)

    assertlib.assert_absent("vrf0")


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for infiniband test",
)
def test_add_ib_pkey_nic_and_remove():
    test_nic = os.environ["TEST_REAL_NIC"]
    with example_state(
        "infiniband_pkey_ipoib_create.yml",
        cleanup="infiniband_pkey_ipoib_delete.yml",
        substitute=("mlx5_ib0", test_nic),
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent(f"{test_nic}.80ff")


def test_add_mac_vlan_and_remove():
    with example_state(
        "mac_vlan_create.yml", cleanup="mac_vlan_absent.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("macvlan0")


def test_add_mac_vtap_and_remove():
    with example_state(
        "mac_vtap_create.yml", cleanup="mac_vtap_absent.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("macvtap0")


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.28,
    reason="Modifying veth is not supported on lower NetworkManager versions.",
)
def test_add_veth_and_remove():
    with example_state(
        "veth1_up.yml", cleanup="veth1_absent.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("veth1")
    assertlib.assert_absent("veth1peer")


@pytest.mark.skipif(
    nm_major_minor_version() <= 1.30,
    reason="Generating config is not supported on NetworkManager 1.30-",
)
@pytest.mark.tier1
def test_gen_conf_for_examples():
    example_dir = find_examples_dir()
    with os.scandir(example_dir) as example_dir_fd:
        for example_file in example_dir_fd:
            if example_file.name.endswith(".yml"):
                first_result = libnmstate.generate_configurations(
                    load_example(example_file.name)
                )
                second_result = libnmstate.generate_configurations(
                    load_example(example_file.name)
                )
                assert first_result == second_result


@pytest.mark.tier1
def test_add_macsec_and_remove(eth1_up):
    with example_state(
        "macsec0_up.yml", cleanup="macsec0_absent.yml"
    ) as desired_state:
        assertlib.assert_state(desired_state)

    assertlib.assert_absent("macsec0")


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="NM cannot change hostname in container",
)
def test_static_hostname_for_examples():
    with example_state(
        "static_hostname.yml", cleanup="dynamic_hostname.yml"
    ) as desired_state:
        cur_hostname = libnmstate.show()[HostNameState.KEY]
        assert cur_hostname == desired_state[HostNameState.KEY]
