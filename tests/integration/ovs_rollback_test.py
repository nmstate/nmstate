# SPDX-License-Identifier: Apache-2.0

import copy
import time

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Bridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import Route
from libnmstate.schema import VLAN

from .testlib import statelib
from .testlib.assertlib import RETRY_COUNT

BR_EX = "br-ex"
BOND1 = "bond1"
VLAN_IFNAME = "eth101"
BR_EX_IPV4 = "192.0.2.1"


def _br_ex_ovs_interface():
    return {
        Interface.NAME: BR_EX,
        Interface.TYPE: InterfaceType.OVS_INTERFACE,
        Interface.STATE: InterfaceState.UP,
        Interface.IPV4: {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: BR_EX_IPV4,
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        },
    }


def _br_ex_ovs_bridge(uplink_port):
    return {
        Interface.NAME: BR_EX,
        Interface.TYPE: InterfaceType.OVS_BRIDGE,
        Interface.STATE: InterfaceState.UP,
        OVSBridge.CONFIG_SUBTREE: {
            OVSBridge.OPTIONS_SUBTREE: {
                OVSBridge.Options.STP: {Bridge.STP.ENABLED: False}
            },
            OVSBridge.PORT_SUBTREE: [
                {OVSBridge.Port.NAME: BR_EX},
                {OVSBridge.Port.NAME: uplink_port},
            ],
        },
    }


def _br_ex_over_vlan_of_ethernet_state():
    return {
        Interface.KEY: [
            {
                Interface.NAME: VLAN_IFNAME,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.VLAN,
                VLAN.CONFIG_SUBTREE: {
                    VLAN.ID: 101,
                    VLAN.BASE_IFACE: "eth1",
                },
            },
            _br_ex_ovs_interface(),
            _br_ex_ovs_bridge(VLAN_IFNAME),
        ]
    }


def _br_ex_over_bond_state():
    return {
        Interface.KEY: [
            {
                Interface.NAME: BOND1,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.BOND,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ACTIVE_BACKUP,
                    Bond.OPTIONS_SUBTREE: {
                        "miimon": "140",
                        "primary": "eth1",
                    },
                    Bond.PORT: ["eth1", "eth2"],
                },
            },
            _br_ex_ovs_interface(),
            _br_ex_ovs_bridge(BOND1),
        ]
    }


def _br_ex_over_vlan_of_bond_state():
    return {
        Interface.KEY: [
            {
                Interface.NAME: BOND1,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.BOND,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ACTIVE_BACKUP,
                    Bond.OPTIONS_SUBTREE: {
                        "miimon": "140",
                        "primary": "eth1",
                    },
                    Bond.PORT: ["eth1", "eth2"],
                },
            },
            {
                Interface.NAME: VLAN_IFNAME,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.VLAN,
                VLAN.CONFIG_SUBTREE: {
                    VLAN.ID: 101,
                    VLAN.BASE_IFACE: BOND1,
                },
            },
            _br_ex_ovs_interface(),
            _br_ex_ovs_bridge(VLAN_IFNAME),
        ]
    }


def _get_iface(state, iface_type):
    return next(
        iface
        for iface in state[Interface.KEY]
        if iface[Interface.TYPE] == iface_type
    )


def _lookup_iface_by_name_and_type(ifaces, name, iface_type):
    return next(
        (
            iface
            for iface in ifaces
            if iface[Interface.NAME] == name
            and iface[Interface.TYPE] == iface_type
        ),
        None,
    )


def _sort_ovs_bridge_ports(iface):
    ports = (
        iface.get(OVSBridge.CONFIG_SUBTREE, {}).get(OVSBridge.PORT_SUBTREE)
        or []
    )
    ports.sort(key=lambda port: port.get(OVSBridge.Port.NAME, ""))


def _assert_interface_state_match(expected_iface):
    """
    Match one interface by (name, type).

    Important for br-ex where the OVS bridge and OVS interface share a name:
    assert_state()/assert_state_match() key only on name and can conflate them.
    """
    name = expected_iface[Interface.NAME]
    iface_type = expected_iface[Interface.TYPE]
    expected = copy.deepcopy(expected_iface)
    _sort_ovs_bridge_ports(expected)

    for i in range(RETRY_COUNT):
        current_iface = _lookup_iface_by_name_and_type(
            libnmstate.show(include_secrets=True)[Interface.KEY],
            name,
            iface_type,
        )
        if current_iface is not None:
            current = copy.deepcopy(current_iface)
            _sort_ovs_bridge_ports(current)
            # Interface state can flap briefly during rollback; assertlib also
            # ignores it during verify.
            expected.pop(Interface.STATE, None)
            current.pop(Interface.STATE, None)
            desired_state = statelib.State({Interface.KEY: [expected]})
            current_state = statelib.State({Interface.KEY: [current]})
            desired_state.normalize()
            current_state.normalize()
            if desired_state.match(current_state):
                return
            if i == RETRY_COUNT - 1:
                print(
                    f"interface {name}/{iface_type} mismatch:\n"
                    f"desired={desired_state.state}\n"
                    f"current={current_state.state}"
                )
                assert desired_state.match(current_state)
        elif i == RETRY_COUNT - 1:
            raise AssertionError(
                f"Interface {name} with type {iface_type} not found"
            )
        time.sleep(0.5)


def _assert_interfaces_state_match(expected_ifaces):
    for expected_iface in expected_ifaces:
        _assert_interface_state_match(expected_iface)


def _enable_stp(modified_state):
    bridge_iface = _get_iface(modified_state, InterfaceType.OVS_BRIDGE)
    bridge_iface[OVSBridge.CONFIG_SUBTREE][OVSBridge.OPTIONS_SUBTREE][
        OVSBridge.Options.STP
    ][Bridge.STP.ENABLED] = True


def _set_route_verification_failure(modified_state, ovs_iface):
    # Match test_route_delayed_by_nm_fails: DHCP without a working server
    # leaves the static route unverifiable, so apply fails after the
    # checkpoint is created and nmstate rolls back.
    ovs_iface[Interface.IPV4] = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.DHCP: True,
    }
    modified_state[Route.KEY] = {
        Route.CONFIG: [
            {
                Route.DESTINATION: "203.0.113.0/24",
                Route.NEXT_HOP_ADDRESS: "192.0.2.251",
                Route.NEXT_HOP_INTERFACE: BR_EX,
            }
        ]
    }


def _trigger_post_apply_verification_failure(modified_state):
    _enable_stp(modified_state)
    ovs_iface = _get_iface(modified_state, InterfaceType.OVS_INTERFACE)
    _set_route_verification_failure(modified_state, ovs_iface)


def _assert_rollback_after_failed_modification(initial_state):
    topology_ifaces = initial_state[Interface.KEY]

    libnmstate.apply(initial_state)
    _assert_interfaces_state_match(topology_ifaces)

    modified_state = copy.deepcopy(initial_state)
    _trigger_post_apply_verification_failure(modified_state)

    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(modified_state)

    time.sleep(5)
    # Compare desired topology only (by name+type). A full show() snapshot
    # includes ephemeral runtime fields that often differ after rollback.
    _assert_interfaces_state_match(topology_ifaces)


@pytest.fixture
def cleanup_br_ex_topology():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BR_EX,
                    Interface.TYPE: InterfaceType.OVS_BRIDGE,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: BOND1,
                    Interface.TYPE: InterfaceType.BOND,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: VLAN_IFNAME,
                    Interface.TYPE: InterfaceType.VLAN,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


# OCP day1: br-ex over VLAN of ethernet
@pytest.mark.tier1
def test_rollback_br_ex_over_vlan_of_ethernet(cleanup_br_ex_topology, eth1_up):
    _assert_rollback_after_failed_modification(
        _br_ex_over_vlan_of_ethernet_state()
    )


# OCP day1: br-ex over bond (active-backup mode)
@pytest.mark.tier1
def test_rollback_br_ex_over_bond(cleanup_br_ex_topology, eth1_up, eth2_up):
    _assert_rollback_after_failed_modification(_br_ex_over_bond_state())


# OCP day1: br-ex over VLAN of bond
@pytest.mark.tier1
def test_rollback_br_ex_over_vlan_of_bond(
    cleanup_br_ex_topology, eth1_up, eth2_up
):
    _assert_rollback_after_failed_modification(
        _br_ex_over_vlan_of_bond_state()
    )
