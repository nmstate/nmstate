# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest
import yaml

import libnmstate

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import VRF

from .testlib import assertlib
from .testlib import cmdlib
from .testlib.apply import apply_with_description


TEST_VRF0 = "test-vrf0"
TEST_VRF1 = "test-vrf1"
TEST_VRF_PORT0 = "eth1"
TEST_VRF_PORT1 = "eth2"
TEST_VRF_VETH0 = "veth0"
TEST_VRF_VETH1 = "veth1"
TEST_ROUTE_TABLE_ID0 = 100
TEST_ROUTE_TABLE_ID1 = 101
IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"
TEST_MAC_ADDRESS = "00:00:5E:00:53:01"
TEST_BOND0 = "test-bond0"
TEST_BOND0_VLAN = "test-bond0.100"


@pytest.fixture
def vrf0_with_port0(port1_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF0,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: [TEST_VRF_PORT0],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID0,
        },
    }
    apply_with_description(
        "Create the vrf interface test-vrf0 with vrf port eth1 and vrf route "
        "table ID 100",
        {Interface.KEY: [vrf_iface_info]},
    )
    yield vrf_iface_info
    apply_with_description(
        "Delete the vrf interface test-vrf0",
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        },
    )

    assertlib.assert_absent(TEST_VRF0)


@pytest.fixture
def vrf1_with_port1(port1_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF1,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: [TEST_VRF_PORT1],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID1,
        },
    }
    apply_with_description(
        "Create the vrf interface test-vrf1 with vrf port eth2 and vrf route "
        "table ID 101",
        {Interface.KEY: [vrf_iface_info]},
    )
    yield vrf_iface_info
    apply_with_description(
        "Delete the vrf interface test-vrf1",
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        },
    )

    assertlib.assert_absent(TEST_VRF1)


@pytest.fixture
def vrf1_with_eth1_and_eth2(eth1_up, eth2_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF1,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: ["eth1", "eth2"],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID1,
        },
    }
    apply_with_description(
        "Create the vrf interface test-vrf1, attach ports eth1 and eth2 to "
        "it, configure the vrf route table ID 101",
        {Interface.KEY: [vrf_iface_info]},
    )
    yield vrf_iface_info
    apply_with_description(
        "Delete the vrf interface test-vrf1",
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        },
    )

    assertlib.assert_absent(TEST_VRF1)


@pytest.fixture
def unmanaged_port_up():
    cmdlib.exec_cmd(
        f"ip link add {TEST_VRF_VETH0} type veth peer {TEST_VRF_VETH1}".split()
    )
    cmdlib.exec_cmd(f"ip link set {TEST_VRF_VETH0} up".split())
    cmdlib.exec_cmd(f"ip link set {TEST_VRF_VETH1} up".split())
    yield TEST_VRF_VETH0
    cmdlib.exec_cmd(f"ip link del {TEST_VRF_VETH0}".split())
    apply_with_description(
        "Delete the vrf interface test-vrf0 and veth device veth0",
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF_VETH0,
                    Interface.TYPE: InterfaceType.VETH,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: TEST_VRF0,
                    Interface.TYPE: InterfaceType.VRF,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        },
    )


@pytest.fixture
def vrf1_with_unmanaged_port(unmanaged_port_up):
    vrf_iface_info = {
        Interface.NAME: TEST_VRF1,
        Interface.TYPE: InterfaceType.VRF,
        VRF.CONFIG_SUBTREE: {
            VRF.PORT_SUBTREE: [unmanaged_port_up],
            VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID1,
        },
    }
    veth_iface_info = {
        Interface.NAME: unmanaged_port_up,
        Interface.TYPE: InterfaceType.ETHERNET,
        Interface.STATE: InterfaceState.UP,
    }
    apply_with_description(
        f"Attach ethernet {unmanaged_port_up} to the vrf interface test-vrf1 "
        "and set vrf route table ID to 101",
        {Interface.KEY: [vrf_iface_info, veth_iface_info]},
    )
    try:
        yield vrf_iface_info
    finally:
        apply_with_description(
            "Delete the test-vrf1 interface",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VRF1,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
        )


@pytest.fixture
def vrf_over_bond_vlan(eth1_up, eth2_up):
    desired = yaml.load(
        """---
        interfaces:
        - name: test-bond0.100
          type: vlan
          vlan:
            base-iface: test-bond0
            id: 100
        - name: test-bond0
          type: bond
          link-aggregation:
            mode: balance-rr
        - name: test-vrf0
          type: vrf
          state: up
          vrf:
            port:
            - test-bond0
            - test-bond0.100
            route-table-id: 100
        """,
        Loader=yaml.SafeLoader,
    )
    apply_with_description(
        "Create the vlan device over test-bond0 with ID 100, "
        "create the bond interface test-bond0 with bonding mode "
        "balance-rr, create the vrf interface test-vrf0 "
        "with ports test-bond0, test-bond0.100, and the vrf route table "
        "id 100",
        desired,
    )
    yield desired
    apply_with_description(
        "Delete the vlan interface test-bond0.100, delete the bond interface "
        "test-bond0, delete the vrf interface test-vrf0",
        yaml.load(
            """---
            interfaces:
            - name: test-bond0.100
              type: vlan
              state: absent
            - name: test-bond0
              type: bond
              state: absent
            - name: test-vrf0
              type: vrf
              state: absent
            """,
            Loader=yaml.SafeLoader,
        ),
    )


class TestVrf:
    def test_create_and_remove(self, vrf0_with_port0):
        pass

    def test_sort_ports(self, vrf1_with_eth1_and_eth2):
        iface_info = vrf1_with_eth1_and_eth2
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].reverse()
        desired_state = {Interface.KEY: [iface_info]}
        libnmstate.apply(desired_state)
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].sort()
        assertlib.assert_state_match({Interface.KEY: [iface_info]})

    def test_change_route_table_id(self, vrf0_with_port0):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.ROUTE_TABLE_ID] += 1
        desired_state = {Interface.KEY: [iface_info]}
        apply_with_description(
            "Configure the vrf device test-vrf0 with vrf "
            "route table ID 101",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_create_with_empty_ports(self):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF0,
                    Interface.TYPE: InterfaceType.VRF,
                    VRF.CONFIG_SUBTREE: {
                        VRF.PORT_SUBTREE: [],
                        VRF.ROUTE_TABLE_ID: TEST_ROUTE_TABLE_ID0,
                    },
                }
            ]
        }
        apply_with_description(
            "Create the vrf interface test-vrf0 with the empty ports and the "
            "vrf route table ID 100",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)
        apply_with_description(
            "Delete the vrf interface test-vrf0",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VRF0,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            },
        )
        assertlib.assert_absent(TEST_VRF0)

    def test_add_and_remove_port(self, vrf0_with_port0, port1_up):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].append(TEST_VRF_PORT1)
        desired_state = {Interface.KEY: [iface_info]}
        apply_with_description(
            "Attach ethernet eth1 and eth2 to the vrf interface test-vrf0",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE].remove(TEST_VRF_PORT1)
        desired_state = {Interface.KEY: [iface_info]}
        apply_with_description(
            "Attach ethernet eth1 to the vrf interface test-vrf0",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_remove_port(self, vrf0_with_port0):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = []
        desired_state = {Interface.KEY: [iface_info]}
        apply_with_description(
            "Set the empty port for the vrf interface test-vrf0",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_remove_all_ports(self, vrf0_with_port0):
        iface_info = vrf0_with_port0
        iface_info[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = []
        desired_state = {Interface.KEY: [iface_info]}
        apply_with_description(
            "Set the empty port for the vrf interface test-vrf0",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_moving_port_from_other_vrf(
        self, vrf0_with_port0, vrf1_with_port1
    ):
        vrf0_iface = vrf0_with_port0
        vrf1_iface = vrf1_with_port1
        vrf0_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = []
        vrf1_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [
            TEST_VRF_PORT0,
            TEST_VRF_PORT1,
        ]

        desired_state = {Interface.KEY: [vrf0_iface, vrf1_iface]}
        apply_with_description(
            "Configure the vrf interface test-vrf0 with empty port, "
            "configure the vrf interface test-vrf1 with the vrf "
            "port eth1 and eth2",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_swaping_port(self, vrf0_with_port0, vrf1_with_port1):
        vrf0_iface = vrf0_with_port0
        vrf1_iface = vrf1_with_port1
        vrf0_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [TEST_VRF_PORT1]
        vrf1_iface[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] = [TEST_VRF_PORT0]
        desired_state = {Interface.KEY: [vrf0_iface, vrf1_iface]}
        apply_with_description(
            "Attach ethernet eth2 to the vrf interface test-vrf0, "
            "attach ethernet eth1 to the vrf interface test-vrf1",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_port_holding_ip(self, vrf0_with_port0):
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_VRF_PORT0,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: False,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: False,
                        InterfaceIPv6.AUTOCONF: False,
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                    },
                }
            ]
        }
        apply_with_description(
            "Create the eth1 interface with address 192.0.2.251/24 and "
            "2001:db8:1::1/64 configured",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)

    def test_takes_over_unmanaged_vrf(self, vrf1_with_unmanaged_port):
        pass

    def test_vrf_ignore_mac_address(self, vrf0_with_port0):
        apply_with_description(
            "Create the test-vrf0 with the MAC address 00:00:5E:00:53:01 "
            "configured",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VRF0,
                        Interface.MAC: TEST_MAC_ADDRESS,
                    }
                ]
            },
        )

    def test_vrf_ignore_accept_all_mac_addresses_false(self, vrf0_with_port0):
        apply_with_description(
            "Create the test-vrf0 with accepting all MAC address disabled",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VRF0,
                        Interface.ACCEPT_ALL_MAC_ADDRESSES: False,
                    }
                ]
            },
        )

    def test_change_vrf_without_table_id(self, vrf0_with_port0):
        apply_with_description(
            "Create the test-vrf0 with port eth1 attached",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VRF0,
                        VRF.CONFIG_SUBTREE: {
                            VRF.PORT_SUBTREE: [TEST_VRF_PORT0],
                        },
                    }
                ]
            },
        )

    def test_new_vrf_without_table_id(self):
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: TEST_VRF0,
                            VRF.CONFIG_SUBTREE: {
                                VRF.PORT_SUBTREE: [TEST_VRF_PORT0],
                            },
                        }
                    ]
                }
            )

    def test_new_vrf_over_new_bond_vlan(self, vrf_over_bond_vlan):
        assertlib.assert_state_match(vrf_over_bond_vlan)

    def test_vrf_over_bond_vlan_got_auto_remove_by_parent(
        self, vrf_over_bond_vlan
    ):
        apply_with_description(
            "Remove the vrf device test-vrf0 and the bond device test-bond0",
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VRF0,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                    {
                        Interface.NAME: TEST_BOND0,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                ]
            },
        )
        assertlib.assert_absent(TEST_VRF0)
        assertlib.assert_absent(TEST_BOND0)
        assertlib.assert_absent(TEST_BOND0_VLAN)
