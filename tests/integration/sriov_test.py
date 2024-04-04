# SPDX-License-Identifier: LGPL-2.1-or-later

import copy
import os

import pytest

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import Ethernet
from libnmstate.schema import Ethtool
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge
from libnmstate.schema import OVSBridge

from .testlib import assertlib
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import add_port_to_bridge
from .testlib.bridgelib import create_bridge_subtree_state
from .testlib.bridgelib import linux_bridge
from .testlib.ovslib import ovs_bridge
from .testlib.ovslib import ovs_bridge_bond
from .testlib.sriov import get_sriov_vf_names
from .testlib.statelib import show_only

MAC1 = "00:11:22:33:44:55"
MAC2 = "00:11:22:33:44:66"
MAC3 = "00:11:22:33:44:FF"
MAC_MIX_CASE = "00:11:22:33:44:Ff"
TEST_BOND = "test-bond0"
TEST_BRIDGE = "test-br0"
TEST_OVS_IFACE = "test-ovs0"

VF0_CONF = {
    Ethernet.SRIOV.VFS.ID: 0,
    Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
    Ethernet.SRIOV.VFS.MAC_ADDRESS: MAC1,
    Ethernet.SRIOV.VFS.TRUST: False,
}

VF1_CONF = {
    Ethernet.SRIOV.VFS.ID: 1,
    Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
    Ethernet.SRIOV.VFS.MAC_ADDRESS: MAC2,
    Ethernet.SRIOV.VFS.TRUST: False,
}


def _test_nic_name():
    return os.environ.get("TEST_REAL_NIC")


def find_vf_iface_name(pf_name, vf_id):
    return os.listdir(
        f"/sys/class/net/{pf_name}/device/virtfn{vf_id}/net"
    ).pop()


@pytest.fixture
def disable_sriov():
    pf_name = _test_nic_name()
    iface_info = {
        Interface.NAME: pf_name,
        Interface.STATE: InterfaceState.UP,
        Ethernet.CONFIG_SUBTREE: {
            Ethernet.SRIOV_SUBTREE: {
                Ethernet.SRIOV.TOTAL_VFS: 0,
                Ethernet.SRIOV.VFS_SUBTREE: [],
            }
        },
    }
    desired_state = {Interface.KEY: [iface_info]}
    libnmstate.apply(desired_state)
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.fixture
def sriov_interface(disable_sriov):
    pf_name = _test_nic_name()
    iface_info = {
        Interface.NAME: pf_name,
        Interface.STATE: InterfaceState.UP,
        Ethernet.CONFIG_SUBTREE: {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2},
        },
    }
    desired_state = {Interface.KEY: [iface_info]}
    libnmstate.apply(desired_state)
    yield desired_state


@pytest.fixture
def sriov_iface_vf(disable_sriov):
    pf_name = _test_nic_name()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: pf_name,
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {
                        Ethernet.SRIOV.TOTAL_VFS: 2,
                        Ethernet.SRIOV.VFS_SUBTREE: [VF0_CONF, VF1_CONF],
                    }
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    yield desired_state


@pytest.fixture
def sriov_with_62_vfs():
    pf_name = _test_nic_name()
    iface_info = {
        Interface.NAME: pf_name,
        Interface.STATE: InterfaceState.UP,
        Ethernet.CONFIG_SUBTREE: {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 62},
        },
    }
    desired_state = {Interface.KEY: [iface_info]}
    libnmstate.apply(desired_state)
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
class TestSrIov:
    def test_sriov_with_no_vfs_config(self, sriov_interface):
        assertlib.assert_state_match(sriov_interface)

    def test_sriov_increase_vfs(self, sriov_interface):
        desired_state = sriov_interface
        eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
        eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 5
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_sriov_decrease_vfs(self, sriov_interface):
        desired_state = sriov_interface
        eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
        eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 1
        eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = [
            VF0_CONF
        ]
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_sriov_create_vf_config(self, sriov_iface_vf):
        assertlib.assert_state_match(sriov_iface_vf)

    def test_sriov_edit_vf_config(self, sriov_iface_vf):
        desired_state = sriov_iface_vf
        eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
        vf0 = eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE][0]
        vf0[Ethernet.SRIOV.VFS.TRUST] = True
        vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = MAC3
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)

    def test_sriov_remove_vf_config(self, sriov_iface_vf):
        desired_state = sriov_iface_vf
        eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
        eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = []
        libnmstate.apply(desired_state)

    def test_sriov_vf_mac_mixed_case(self, sriov_iface_vf):
        desired_state = sriov_iface_vf
        eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
        vf0 = eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE][0]
        vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = MAC_MIX_CASE
        libnmstate.apply(desired_state)

        vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = MAC_MIX_CASE.upper()
        assertlib.assert_state_match(desired_state)

    def test_wait_sriov_vf_been_created(self):
        pf_name = _test_nic_name()
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Ethernet.CONFIG_SUBTREE: {
                        Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
                    },
                }
            ]
        }
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
            vf_ifaces = get_sriov_vf_names(pf_name)
            assert len(vf_ifaces) == 2

        finally:
            desired_state[Interface.KEY][0][
                Interface.STATE
            ] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

    def test_wait_sriov_vf_been_deleted_when_total_vfs_decrease(self):
        pf_name = _test_nic_name()
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Ethernet.CONFIG_SUBTREE: {
                        Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
                    },
                }
            ]
        }
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
            vf_ifaces = get_sriov_vf_names(pf_name)
            assert len(vf_ifaces) == 2

            desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE][
                Ethernet.SRIOV_SUBTREE
            ][Ethernet.SRIOV.TOTAL_VFS] = 1
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
            vf_ifaces = get_sriov_vf_names(pf_name)
            assert len(vf_ifaces) == 1

        finally:
            desired_state[Interface.KEY][0][
                Interface.STATE
            ] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

    def test_sriov_vf_vlan_id_and_qos_proto(self):
        pf_name = _test_nic_name()
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Ethernet.CONFIG_SUBTREE: {
                        Ethernet.SRIOV_SUBTREE: {
                            Ethernet.SRIOV.TOTAL_VFS: 2,
                            Ethernet.SRIOV.VFS_SUBTREE: [
                                {
                                    Ethernet.SRIOV.VFS.ID: 0,
                                    Ethernet.SRIOV.VFS.VLAN_ID: 100,
                                    Ethernet.SRIOV.VFS.QOS: 5,
                                    Ethernet.SRIOV.VFS.VLAN_PROTO: "802.1ad",
                                },
                                {
                                    Ethernet.SRIOV.VFS.ID: 1,
                                    Ethernet.SRIOV.VFS.VLAN_ID: 102,
                                    Ethernet.SRIOV.VFS.QOS: 6,
                                    Ethernet.SRIOV.VFS.VLAN_PROTO: "802.1q",
                                },
                            ],
                        }
                    },
                }
            ]
        }
        try:
            libnmstate.apply(desired_state)
        finally:
            desired_state[Interface.KEY][0][
                Interface.STATE
            ] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

    def test_refer_vf_using_pf_name_and_vf_id(self, sriov_interface):
        pf_name = _test_nic_name()
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: f"sriov:{pf_name}:0",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.MTU: 1280,
                },
                {
                    Interface.NAME: f"sriov:{pf_name}:1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.MTU: 1281,
                },
            ]
        }
        expected_state = copy.deepcopy(desired_state)
        expected_state[Interface.KEY][0][Interface.NAME] = find_vf_iface_name(
            pf_name, 0
        )
        expected_state[Interface.KEY][1][Interface.NAME] = find_vf_iface_name(
            pf_name, 1
        )
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(expected_state)
        finally:
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: expected_state[Interface.KEY][0][
                                Interface.NAME
                            ],
                            Interface.STATE: InterfaceState.ABSENT,
                        },
                        {
                            Interface.NAME: expected_state[Interface.KEY][0][
                                Interface.NAME
                            ],
                            Interface.STATE: InterfaceState.ABSENT,
                        },
                    ]
                }
            )

    def test_refer_vf_using_pf_name_and_vf_id_bond(self, sriov_interface):
        pf_name = _test_nic_name()
        with bond_interface(
            TEST_BOND, [f"sriov:{pf_name}:0", f"sriov:{pf_name}:1"]
        ) as expected_state:
            expected_state[Interface.KEY][0][Bond.CONFIG_SUBTREE][
                Bond.PORT
            ] = [
                find_vf_iface_name(pf_name, 0),
                find_vf_iface_name(pf_name, 1),
            ]
            assertlib.assert_state_match(expected_state)

    def test_refer_vf_using_pf_name_and_vf_id_linux_bridge(
        self, sriov_interface
    ):
        pf_name = _test_nic_name()
        bridge_state = create_bridge_subtree_state()
        add_port_to_bridge(bridge_state, f"sriov:{pf_name}:0")
        add_port_to_bridge(bridge_state, f"sriov:{pf_name}:1")
        # Disable STP to avoid topology changes and the consequence link change
        options_subtree = bridge_state[LinuxBridge.OPTIONS_SUBTREE]
        options_subtree[LinuxBridge.STP_SUBTREE][
            LinuxBridge.STP.ENABLED
        ] = False
        with linux_bridge(TEST_BRIDGE, bridge_state) as expected_state:
            expected_state[Interface.KEY][0][LinuxBridge.CONFIG_SUBTREE][
                LinuxBridge.PORT_SUBTREE
            ] = [
                {
                    LinuxBridge.Port.NAME: port_name,
                }
                for port_name in (
                    find_vf_iface_name(pf_name, 0),
                    find_vf_iface_name(pf_name, 1),
                )
            ]
            assertlib.assert_state_match(expected_state)

    def test_refer_vf_using_pf_name_and_vf_id_ovs_bridge(
        self, sriov_interface
    ):
        pf_name = _test_nic_name()
        with ovs_bridge(
            TEST_BRIDGE,
            [f"sriov:{pf_name}:0", f"sriov:{pf_name}:1"],
            TEST_OVS_IFACE,
        ) as expected_state:
            expected_state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE][
                OVSBridge.PORT_SUBTREE
            ] = [
                {
                    OVSBridge.Port.NAME: port_name,
                }
                for port_name in (
                    find_vf_iface_name(pf_name, 0),
                    find_vf_iface_name(pf_name, 1),
                    TEST_OVS_IFACE,
                )
            ]
            assertlib.assert_state_match(expected_state)

    def test_refer_vf_using_pf_name_and_vf_id_ovs_bond(self, sriov_interface):
        pf_name = _test_nic_name()
        with ovs_bridge_bond(
            TEST_BRIDGE,
            {TEST_BOND: [f"sriov:{pf_name}:0", f"sriov:{pf_name}:1"]},
            TEST_OVS_IFACE,
        ) as expected_state:
            ports = [
                {OVSBridge.Port.LinkAggregation.Port.NAME: port_name}
                for port_name in (
                    find_vf_iface_name(pf_name, 0),
                    find_vf_iface_name(pf_name, 1),
                )
            ]
            expected_state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE][
                OVSBridge.PORT_SUBTREE
            ] = [
                {
                    OVSBridge.Port.NAME: TEST_BOND,
                    OVSBridge.Port.LINK_AGGREGATION_SUBTREE: {
                        OVSBridge.Port.LinkAggregation.PORT_SUBTREE: ports,
                    },
                },
                {OVSBridge.Port.NAME: TEST_OVS_IFACE},
            ]
            assertlib.assert_state_match(expected_state)

    def test_sriov_partial_editing_vf(self, sriov_iface_vf):
        expected_state = copy.deepcopy(sriov_iface_vf)
        expected_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE][
            Ethernet.SRIOV_SUBTREE
        ][Ethernet.SRIOV.VFS_SUBTREE][1][Ethernet.SRIOV.VFS.TRUST] = True

        iface_name = sriov_iface_vf[Interface.KEY][0][Interface.NAME]
        eth_config = sriov_iface_vf[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
        vf_conf = eth_config[Ethernet.SRIOV_SUBTREE][
            Ethernet.SRIOV.VFS_SUBTREE
        ][1]
        vf_conf[Ethernet.SRIOV.VFS.TRUST] = True
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: iface_name,
                    Ethernet.CONFIG_SUBTREE: {
                        Ethernet.SRIOV_SUBTREE: {
                            Ethernet.SRIOV.VFS_SUBTREE: [vf_conf]
                        }
                    },
                }
            ]
        }
        libnmstate.apply(desired_state)

        assertlib.assert_state_match(expected_state)

    def test_enable_sriov_and_use_future_vf(self, disable_sriov):
        pf_name = _test_nic_name()
        iface_infos = [
            {
                Interface.NAME: pf_name,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2},
                },
            },
            {
                Interface.NAME: f"sriov:{pf_name}:0",
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: False,
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: False,
                },
            },
            {
                Interface.NAME: f"sriov:{pf_name}:1",
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: False,
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: False,
                },
            },
        ]
        desired_state = {Interface.KEY: iface_infos}
        libnmstate.apply(desired_state)

    # Changing VF from 62 to 63 require massive time as kernel require us
    # to disable SRIOV before changing VF count, this test is focus on
    # whether nmstate has enough verification retry.
    def test_change_vf_from_62_to_63(self, sriov_with_62_vfs):
        pf_name = _test_nic_name()
        iface_info = {
            Interface.NAME: pf_name,
            Interface.STATE: InterfaceState.UP,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 63},
            },
        }
        desired_state = {Interface.KEY: [iface_info]}
        libnmstate.apply(desired_state)

    def test_change_vf_parameters_only(self, sriov_with_62_vfs):
        pf_name = _test_nic_name()
        cur_iface = show_only((pf_name,))[Interface.KEY][0]
        iface_infos = [
            {
                Interface.NAME: pf_name,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Ethtool.CONFIG_SUBTREE: cur_iface[Ethtool.CONFIG_SUBTREE],
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {
                        Ethernet.SRIOV.VFS_SUBTREE: [VF0_CONF, VF1_CONF],
                    }
                },
            },
        ]
        desired_state = {Interface.KEY: iface_infos}
        libnmstate.apply(desired_state)
        vf_ifaces = get_sriov_vf_names(pf_name)
        assert len(vf_ifaces) == 62

    def test_drivers_autoprobe_false(self):
        pf_name = _test_nic_name()
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Ethernet.CONFIG_SUBTREE: {
                        Ethernet.SRIOV_SUBTREE: {
                            Ethernet.SRIOV.DRIVERS_AUTOPROBE: False,
                            Ethernet.SRIOV.TOTAL_VFS: 32,
                        },
                    },
                }
            ]
        }
        libnmstate.apply(desired_state)
        vf_ifaces = get_sriov_vf_names(pf_name)
        assert len(vf_ifaces) == 0

    def test_drivers_autoprobe_restore_default(self):
        pf_name = _test_nic_name()
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Ethernet.CONFIG_SUBTREE: {
                        Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2},
                    },
                }
            ]
        }
        libnmstate.apply(desired_state)
        vf_ifaces = get_sriov_vf_names(pf_name)
        assert len(vf_ifaces) == 2
