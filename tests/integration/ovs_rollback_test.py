# SPDX-License-Identifier: Apache-2.0

import copy
import time

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateValueError
from libnmstate.schema import Bridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge

from .testlib import assertlib
from .testlib.assertlib import assert_state
from .testlib.yaml import load_yaml

BR_EX = "br-ex"
BOND1 = "bond1"
VLAN_IFNAME = "eth101"


def _br_ex_over_vlan_of_ethernet_state():
    return load_yaml(
        f"""---
        interfaces:
        - name: {VLAN_IFNAME}
          state: up
          type: vlan
          vlan:
            id: 101
            base-iface: eth1
        - name: {BR_EX}
          type: ovs-interface
          state: up
          ipv4:
            enabled: false
        - name: {BR_EX}
          type: ovs-bridge
          state: up
          bridge:
            options:
              stp:
                enabled: false
            port:
            - name: {BR_EX}
            - name: {VLAN_IFNAME}
        """
    )


def _br_ex_over_bond_state():
    return load_yaml(
        f"""---
        interfaces:
        - name: {BOND1}
          state: up
          type: bond
          link-aggregation:
            mode: active-backup
            options:
              miimon: 140
              primary: eth1
            port:
            - eth1
            - eth2
        - name: {BR_EX}
          type: ovs-interface
          state: up
          ipv4:
            enabled: false
        - name: {BR_EX}
          type: ovs-bridge
          state: up
          bridge:
            options:
              stp:
                enabled: false
            port:
            - name: {BR_EX}
            - name: {BOND1}
        """
    )


def _br_ex_over_vlan_of_bond_state():
    return load_yaml(
        f"""---
        interfaces:
        - name: {VLAN_IFNAME}
          state: up
          type: vlan
          vlan:
            id: 101
            base-iface: eth1
        - name: {BOND1}
          state: up
          type: bond
          link-aggregation:
            mode: active-backup
            port:
            - {VLAN_IFNAME}
        - name: {BR_EX}
          type: ovs-interface
          state: up
          ipv4:
            enabled: false
        - name: {BR_EX}
          type: ovs-bridge
          state: up
          bridge:
            options:
              stp:
                enabled: false
            port:
            - name: {BR_EX}
            - name: {BOND1}
        """
    )


def _assert_rollback_after_failed_modification(initial_state):
    libnmstate.apply(initial_state)
    assertlib.assert_state_match(initial_state)

    current_state = libnmstate.show()

    modified_state = copy.deepcopy(initial_state)
    bridge_iface = next(
        iface
        for iface in modified_state[Interface.KEY]
        if iface[Interface.NAME] == BR_EX
        and iface[Interface.TYPE] == InterfaceType.OVS_BRIDGE
    )
    bridge_iface[OVSBridge.CONFIG_SUBTREE][OVSBridge.OPTIONS_SUBTREE][
        OVSBridge.Options.STP
    ][Bridge.STP.ENABLED] = True
    modified_state[Interface.KEY][0]["invalid_key"] = "foo"

    with pytest.raises((NmstateVerificationError, NmstateValueError)):
        libnmstate.apply(modified_state)

    time.sleep(5)
    assert_state({Interface.KEY: current_state[Interface.KEY]})


@pytest.fixture
def cleanup_br_ex_over_vlan():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BR_EX,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: VLAN_IFNAME,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


@pytest.fixture
def cleanup_br_ex_over_bond():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BR_EX,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: BOND1,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


@pytest.fixture
def cleanup_br_ex_over_vlan_of_bond():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BR_EX,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: BOND1,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: VLAN_IFNAME,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


# OCP day1: br-ex over VLAN of ethernet
@pytest.mark.tier1
def test_rollback_br_ex_over_vlan_of_ethernet(
    cleanup_br_ex_over_vlan, eth1_up
):
    _assert_rollback_after_failed_modification(
        _br_ex_over_vlan_of_ethernet_state()
    )


# OCP day1: br-ex over bond (active-backup mode)
@pytest.mark.tier1
def test_rollback_br_ex_over_bond(
    cleanup_br_ex_over_bond, eth1_up, eth2_up
):
    _assert_rollback_after_failed_modification(_br_ex_over_bond_state())


# OCP day1: br-ex over VLAN of bond
@pytest.mark.tier1
def test_rollback_br_ex_over_vlan_of_bond(
    cleanup_br_ex_over_vlan_of_bond, eth1_up
):
    _assert_rollback_after_failed_modification(
        _br_ex_over_vlan_of_bond_state()
    )
