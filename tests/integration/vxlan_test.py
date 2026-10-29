# SPDX-License-Identifier: Apache-2.0

import time

import pytest

import libnmstate

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface
from libnmstate.schema import LinuxBridge
from libnmstate.schema import VXLAN

from .testlib import assertlib
from .testlib.apply import apply_with_description
from .testlib.assertlib import assert_state
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import linux_bridge
from .testlib.bridgelib import neigh_suppress_sysfs_value
from .testlib.cmdlib import RC_SUCCESS
from .testlib.cmdlib import exec_cmd
from .testlib.cmdlib import format_exec_cmd_result
from .testlib.env import nm_version_int
from .testlib.env import version_str_to_int
from .testlib.statelib import show_only
from .testlib.vxlan import VxlanState
from .testlib.vxlan import vxlan_interfaces
from .testlib.vxlan import vxlans_absent
from .testlib.vxlan import vxlans_down
from .testlib.vxlan import vxlans_up

VXLAN1_ID = 201
VXLAN2_ID = 202


def test_add_and_remove_vxlan(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
def test_add_and_remove_two_vxlans_on_same_iface(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1"),
        VxlanState(id=VXLAN2_ID, base_if=ifname, remote="192.168.100.2"),
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan_interfaces_name = (
        i[Interface.NAME] for i in desired_state[Interface.KEY]
    )
    assertlib.assert_absent(vxlan_interfaces_name)


@pytest.mark.tier1
def test_add_and_remove_vxlan_without_base_if():
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, remote="192.168.100.1"),
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
def test_add_and_remove_vxlan_nolearning():
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, remote="192.168.100.1", learning=False),
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
@pytest.mark.parametrize("neigh_suppress", [False, True])
def test_show_bridge_vxlan_neigh_suppress(eth1_up, neigh_suppress):
    base_iface = eth1_up[Interface.KEY][0][Interface.NAME]

    vxlan = VxlanState(
        id=75101,
        base_if=base_iface,
        remote="192.0.2.1",
        learning=False,
    )

    bridge_name = "br-evpn"

    bridge_config = {
        LinuxBridge.PORT_SUBTREE: [{LinuxBridge.Port.NAME: vxlan.name}],
        LinuxBridge.OPTIONS_SUBTREE: {
            LinuxBridge.STP_SUBTREE: {LinuxBridge.STP.ENABLED: False}
        },
    }

    with vxlan_interfaces(vxlan):
        with linux_bridge(bridge_name, bridge_config):
            exec_cmd(
                (
                    "bridge",
                    "link",
                    "set",
                    "dev",
                    vxlan.name,
                    "neigh_suppress",
                    "on" if neigh_suppress else "off",
                ),
                check=True,
            )

            assert neigh_suppress_sysfs_value(vxlan.name) == str(
                int(neigh_suppress)
            )

            bridge = show_only((bridge_name,))[Interface.KEY][0]

            port = bridge[LinuxBridge.CONFIG_SUBTREE][
                LinuxBridge.PORT_SUBTREE
            ][0]

            assert port[LinuxBridge.Port.NAME] == vxlan.name
            assert port[LinuxBridge.Port.NEIGH_SUPPRESS] is neigh_suppress


@pytest.mark.tier1
@pytest.mark.parametrize("neigh_suppress", [False, True])
@pytest.mark.xfail(
    nm_version_int() <= version_str_to_int("1.58.1"),
    reason="neighbor-suppress requires NetworkManager > 1.58.1",
    strict=True,
)
def test_apply_bridge_vxlan_neigh_suppress(eth1_up, neigh_suppress):
    base_iface = eth1_up[Interface.KEY][0][Interface.NAME]

    vxlan = VxlanState(
        id=75101,
        base_if=base_iface,
        remote="192.0.2.1",
        learning=False,
    )

    bridge_name = "br-evpn"

    bridge_config = {
        LinuxBridge.PORT_SUBTREE: [
            {
                LinuxBridge.Port.NAME: vxlan.name,
                LinuxBridge.Port.NEIGH_SUPPRESS: not neigh_suppress,
            }
        ],
        LinuxBridge.OPTIONS_SUBTREE: {
            LinuxBridge.STP_SUBTREE: {LinuxBridge.STP.ENABLED: False}
        },
    }

    with vxlan_interfaces(vxlan):
        with linux_bridge(bridge_name, bridge_config) as desired_state:
            assert neigh_suppress_sysfs_value(vxlan.name) == str(
                int(not neigh_suppress)
            )

            port_config = bridge_config[LinuxBridge.PORT_SUBTREE][0]
            port_config[LinuxBridge.Port.NEIGH_SUPPRESS] = neigh_suppress
            libnmstate.apply(desired_state)

            assert neigh_suppress_sysfs_value(vxlan.name) == str(
                int(neigh_suppress)
            )

            bridge = show_only((bridge_name,))[Interface.KEY][0]

            port = bridge[LinuxBridge.CONFIG_SUBTREE][
                LinuxBridge.PORT_SUBTREE
            ][0]

            assert port[LinuxBridge.Port.NAME] == vxlan.name
            assert port[LinuxBridge.Port.NEIGH_SUPPRESS] is neigh_suppress


@pytest.mark.tier1
def test_rollback_for_vxlans(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    current_state = libnmstate.show()
    desired_state = vxlans_up(
        [
            VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1"),
            VxlanState(id=VXLAN2_ID, base_if=ifname, remote="192.168.100.2"),
        ]
    )
    desired_state[Interface.KEY][1]["invalid_key"] = "foo"
    with pytest.raises((NmstateVerificationError, NmstateValueError)):
        libnmstate.apply(desired_state)

    time.sleep(5)  # Give some time for NetworkManager to rollback
    assert_state({Interface.KEY: current_state[Interface.KEY]})


def test_set_vxlan_iface_down(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    vxlan = VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    with vxlan_interfaces(vxlan):
        desired_state = vxlans_down([vxlan])
        apply_with_description(
            "Bring down the vxlan interface eth1.201", desired_state
        )
        assertlib.assert_absent(vxlan.name)


def test_add_new_bond_iface_with_vxlan(eth1_up):
    eth_name = eth1_up[Interface.KEY][0][Interface.NAME]
    bond_name = "bond0"
    vxlan = VxlanState(id=VXLAN1_ID, base_if=bond_name, remote="192.168.100.2")
    with bond_interface(
        name=bond_name, port=[eth_name], extra_iface_state=None, create=False
    ) as bond_desired_state:
        with vxlan_interfaces(vxlan, create=False) as desired_state:
            desired_state[Interface.KEY].append(
                bond_desired_state[Interface.KEY][0]
            )
            apply_with_description(
                "Create bond interface bond0 with bonding mode balance-rr "
                "and port eth1 attached, create the vxlan interface "
                "bond0.201 with vxlan ID 201, remote set to 192.168.100.2, "
                "learning set to true, and the destination-port set to 4789",
                desired_state,
            )
            assertlib.assert_state_match(desired_state)

    assertlib.assert_absent(vxlan.name)
    assertlib.assert_absent(bond_name)


def test_show_vxlan_with_no_remote(eth1_up):
    eth_name = eth1_up[Interface.KEY][0][Interface.NAME]
    vxlan = VxlanState(id=VXLAN1_ID, base_if=eth_name, remote="")
    add_vxlan_cmd = (
        f"ip link add {vxlan.name} type vxlan id {vxlan.id}"
        f" dstport {vxlan.destination_port} dev {eth_name}".split()
    )
    try:
        ret = exec_cmd(add_vxlan_cmd)
        rc, _, _ = ret
        assert rc == RC_SUCCESS, format_exec_cmd_result(ret)
        desired_state = vxlans_down([vxlan])
        assertlib.assert_state(desired_state)
    finally:
        apply_with_description(
            "Remove the vxlan interface eth1.201", vxlans_absent([vxlan])
        )
        assertlib.assert_absent(vxlan.name)


@pytest.mark.tier1
def test_add_and_remove_vxlan_with_no_remote():
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, local="192.168.100.1"),
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
def test_add_vxlan_and_modify_vxlan_id(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    ) as desired_state:
        assertlib.assert_state(desired_state)
        desired_state[Interface.KEY][0][VXLAN.CONFIG_SUBTREE][VXLAN.ID] = 200
        apply_with_description(
            "Set the vxlan ID to 200 for vxlan interface eth1.201",
            desired_state,
        )
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
def test_vxlan_enable_and_disable_accept_all_mac_addresses(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    ) as d_state:
        d_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = True
        apply_with_description(
            "Enable accepting all mac address for vxlan device eth1.201",
            d_state,
        )
        assertlib.assert_state(d_state)

        d_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = False
        apply_with_description(
            "Disable accepting all mac address for vxlan interface eth1.201",
            d_state,
        )
        assertlib.assert_state(d_state)

    vxlan1_ifname = d_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)
