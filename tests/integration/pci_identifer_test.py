# SPDX-License-Identifier: Apache-2.0

import os

import pytest
import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from .testlib.assertlib import assert_state_match
from .testlib.statelib import show_only
from .testlib.yaml import load_yaml

ETH_PROFILE_NAME = "primary-port"
TEST_BOND = "test-bond0"
TEST_VLAN = "test-vlan0"
TEST_BRIDGE = "test-br0"


def _test_nic_name():
    return os.environ["TEST_REAL_NIC"]


def _test_nic_pci():
    iface_name = _test_nic_name()
    iface_state = show_only((iface_name,))[Interface.KEY][0]
    return iface_state[Interface.PCI]


@pytest.fixture
def eth_pci_ref():
    pci_address = _test_nic_pci()
    yield load_yaml(
        f"""---
            name: {ETH_PROFILE_NAME}
            type: ethernet
            identifier: pci-address
            pci-address: "{pci_address}"
        """
    )
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: ETH_PROFILE_NAME,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.fixture
def bond_port_pci_ref():
    yield load_yaml(
        f"""---
        name: {TEST_BOND}
        type: bond
        state: up
        link-aggregation:
          mode: balance-rr
          port:
          - {ETH_PROFILE_NAME}
        """
    )
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_BOND,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.fixture
def vlan_parent_pci_ref():
    yield load_yaml(
        f"""---
        name: {TEST_VLAN}
        type: vlan
        state: up
        vlan:
          base-iface: {ETH_PROFILE_NAME}
          id: 100
        """
    )
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VLAN,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.fixture
def ovs_port_pci_ref():
    yield load_yaml(
        f"""---
        name: {TEST_BRIDGE}
        type: ovs-bridge
        state: up
        bridge:
          ports:
          - name: {ETH_PROFILE_NAME}
        """
    )
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_BRIDGE,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for PCI identifier test",
)
class TestPciIdentifer:
    def test_eth_ref_by_pci(self, eth_pci_ref):
        state = {Interface.KEY: [eth_pci_ref]}
        libnmstate.apply(state)

        iface_name = _test_nic_name()
        pci_address = _test_nic_pci()
        expected_state = load_yaml(
            f"""---
            interfaces:
            - name: {iface_name}
              profile-name: {ETH_PROFILE_NAME}
              type: ethernet
              identifier: pci-address
              pci-address: "{pci_address}"
            """
        )
        assert_state_match(expected_state)

    def test_bond_port_ref_by_pci(self, eth_pci_ref, bond_port_pci_ref):
        state = {Interface.KEY: [eth_pci_ref, bond_port_pci_ref]}
        libnmstate.apply(state)

        iface_name = _test_nic_name()
        pci_address = _test_nic_pci()
        expected_state = load_yaml(
            f"""---
            interfaces:
            - name: {iface_name}
              profile-name: {ETH_PROFILE_NAME}
              type: ethernet
              identifier: pci-address
              pci-address: "{pci_address}"
              controller: {TEST_BOND}
            """
        )
        assert_state_match(expected_state)

    def test_vlan_parent_ref_by_pci(self, eth_pci_ref, vlan_parent_pci_ref):
        state = {Interface.KEY: [eth_pci_ref, vlan_parent_pci_ref]}
        libnmstate.apply(state)

        iface_name = _test_nic_name()
        expected_state = load_yaml(
            f"""---
            interfaces:
            - name: {TEST_VLAN}
              type: vlan
              state: up
              vlan:
                base-iface: {iface_name}
                id: 100
            """
        )
        assert_state_match(expected_state)

    def test_ovs_port_ref_by_pci(self, eth_pci_ref, ovs_port_pci_ref):
        state = {Interface.KEY: [eth_pci_ref, ovs_port_pci_ref]}
        libnmstate.apply(state)

        iface_name = _test_nic_name()
        expected_state = load_yaml(
            f"""---
            interfaces:
            - name: {TEST_BRIDGE}
              type: ovs-bridge
              state: up
              bridge:
                port:
                - name: {iface_name}
            """
        )
        assert_state_match(expected_state)
