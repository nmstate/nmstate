# SPDX-License-Identifier: Apache-2.0

import copy

import pytest

import libnmstate

from libnmstate.error import NmstateValueError
from libnmstate.schema import Bond
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceAltName
from libnmstate.schema import LinuxBridge
from libnmstate.schema import OVSBridge
from libnmstate.schema import Route
from libnmstate.schema import VLAN

from .testlib.bondlib import bond_interface
from .testlib.bridgelib import linux_bridge
from .testlib.cmdlib import exec_cmd
from .testlib.env import is_k8s
from .testlib.iproutelib import get_ip_link_alt_names
from .testlib.ovslib import Bridge as OVSBridgeEnv
from .testlib.retry import retry_till_true_or_timeout
from .testlib.statelib import show_only
from .testlib.statelib import state_match
from .testlib.vlan import vlan_interface
from .testlib.yaml import load_yaml
from .testlib.route import assert_routes

TEST_ALT_NAMES = [
    "port1",
    "reallyreallylonglonglonginterfacenmae",
]

RETRY_TIMEOUT = 10

TEST_BOND_NIC = "bond99"
TEST_BRIDGE_NIC = "br0"
TEST_VLAN_NIC = "vlan101"


@pytest.fixture
def eth1_with_alt_names(eth1_up):
    desired_state = load_yaml(
        """---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          alt-names:
          - name: port1
          - name: reallyreallylonglonglonginterfacenmae
        """
    )
    libnmstate.apply(desired_state)
    yield
    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: eth1
              type: ethernet
              state: up
              alt-names:
              - name: port1
                state: absent
              - name: reallyreallylonglonglonginterfacenmae
                state: absent
            """
        )
    )
    assert get_ip_link_alt_names("eth1") == []


def udev_trigger_check_alt_names(iface_name, expected_alt_names):
    exec_cmd(
        "udevadm trigger --settle --action add "
        f"/sys/class/net/{iface_name}".split(" "),
        check=True,
    )

    return get_ip_link_alt_names(iface_name) == sorted(expected_alt_names)


@pytest.mark.skipif(is_k8s(), reason="K8S does not support alt-names yet")
class TestAltNames:
    # https://issues.redhat.com/browse/RHEL-90096
    @pytest.mark.tier1
    def test_add_and_remove_alt_name(self, eth1_with_alt_names):
        assert get_ip_link_alt_names("eth1") == TEST_ALT_NAMES

    # https://issues.redhat.com/browse/RHEL-90096
    @pytest.mark.tier1
    def test_add_and_remove_extra_alt_name(self, eth1_with_alt_names):
        try:
            libnmstate.apply(
                load_yaml(
                    """---
                    interfaces:
                    - name: eth1
                      type: ethernet
                      state: up
                      alt-names:
                      - name: extra_name
                    """
                )
            )
            assert get_ip_link_alt_names("eth1") == sorted(
                [
                    "extra_name",
                ]
                + TEST_ALT_NAMES
            )
        finally:
            libnmstate.apply(
                load_yaml(
                    """---
                    interfaces:
                    - name: eth1
                      type: ethernet
                      state: up
                      alt-names:
                      - name: extra_name
                        state: absent
                    """
                )
            )
            assert get_ip_link_alt_names("eth1") == TEST_ALT_NAMES

    def test_alt_name_equal_to_iface_name(self, eth1_up):
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                load_yaml(
                    """---
                    interfaces:
                    - name: eth1
                      type: ethernet
                      state: up
                      alt-names:
                      - name: eth1
                    """
                )
            )

    def test_alt_name_not_unique_among_ifaces(self, eth1_up, eth2_up):
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                load_yaml(
                    """---
                            interfaces:
                            - name: eth1
                              type: ethernet
                              state: up
                              alt-names:
                              - name: port1
                            - name: eth2
                              type: ethernet
                              alt-names:
                              - name: port1
                            """
                )
            )

    def test_alt_name_equal_to_other_nic_name(self, eth1_up, eth2_up):
        with pytest.raises(NmstateValueError):
            libnmstate.apply(
                load_yaml(
                    """---
                        interfaces:
                        - name: eth1
                          type: ethernet
                          state: up
                          alt-names:
                          - name: eth2
                        - name: eth2
                          type: ethernet
                        """
                )
            )

    # https://issues.redhat.com/browse/RHEL-90096
    @pytest.mark.tier1
    def test_validate_persistency_of_alt_name(self, eth1_with_alt_names):
        """
        Remove alt name by ip command and udevadm trigger should add it back.
        This simulate OS reboot.
        """
        exec_cmd("ip link property del eth1 altname port1".split(), check=True)
        exec_cmd(
            "ip link property del eth1 altname "
            "reallyreallylonglonglonginterfacenmae".split(),
            check=True,
        )

        retry_till_true_or_timeout(
            RETRY_TIMEOUT, udev_trigger_check_alt_names, "eth1", TEST_ALT_NAMES
        )

    # https://issues.redhat.com/browse/RHEL-126508
    @pytest.mark.tier1
    def test_ref_alt_name_in_bond(self, eth1_with_alt_names):
        with bond_interface(TEST_BOND_NIC, [TEST_ALT_NAMES[0]]):
            iface = show_only((TEST_BOND_NIC,))[Interface.KEY][0]
            assert iface[Bond.CONFIG_SUBTREE][Bond.PORT] == ["eth1"]

    # https://issues.redhat.com/browse/RHEL-126508
    @pytest.mark.tier1
    def test_ref_alt_name_in_linux_bridge(self, eth1_with_alt_names):
        with linux_bridge(TEST_BRIDGE_NIC, {}, ports=[TEST_ALT_NAMES[0]]):
            iface = show_only((TEST_BRIDGE_NIC,))[Interface.KEY][0]
            assert state_match(
                [{"name": "eth1"}],
                iface[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE],
            )

    # https://issues.redhat.com/browse/RHEL-126508
    @pytest.mark.tier1
    def test_ref_alt_name_in_ovs_bridge(self, eth1_with_alt_names):
        ovs_br = OVSBridgeEnv(TEST_BRIDGE_NIC)
        ovs_br.add_system_port(TEST_ALT_NAMES[0])

        with ovs_br.create():
            iface = show_only((TEST_BRIDGE_NIC,))[Interface.KEY][0]
            assert state_match(
                [{"name": "eth1"}],
                iface[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE],
            )

    # https://issues.redhat.com/browse/RHEL-126508
    @pytest.mark.tier1
    def test_ref_alt_name_in_vlan(self, eth1_with_alt_names):
        with vlan_interface(TEST_VLAN_NIC, 101, TEST_ALT_NAMES[0]):
            iface = show_only((TEST_VLAN_NIC,))[Interface.KEY][0]
            assert iface[VLAN.CONFIG_SUBTREE][VLAN.BASE_IFACE] == "eth1"
            assert iface[VLAN.CONFIG_SUBTREE][VLAN.ID] == 101

    # https://issues.redhat.com/browse/RHEL-126508
    @pytest.mark.tier1
    def test_ref_alt_name_in_route(self, eth1_with_alt_names):
        desired_state = load_yaml(
            """---
            routes:
              config:
                - destination: 203.0.113.0/24
                  next-hop-address: 192.0.2.1
                  next-hop-interface: reallyreallylonglonglonginterfacenmae
                  metric: 109
                - destination: 203.0.113.0/24
                  next-hop-address: 192.0.2.2
                  next-hop-interface: port1
                  metric: 109
                - destination: 2001:db8:2::/64
                  next-hop-address: 2001:db8:1::2
                  next-hop-interface: port1
                - destination: 2001:db8:2::/64
                  next-hop-address: 2001:db8:1::3
                  next-hop-interface: reallyreallylonglonglonginterfacenmae
            interfaces:
            - name: eth1
              type: ethernet
              state: up
              ipv4:
                address:
                - ip: 192.0.2.251
                  prefix-length: 24
                dhcp: false
                enabled: true
              ipv6:
                enabled: true
                autoconf: false
                dhcp: false
                address:
                  - ip: 2001:db8:1::1
                    prefix-length: 64
            """
        )
        expected_routes = copy.deepcopy(desired_state[Route.KEY][Route.CONFIG])
        libnmstate.apply(desired_state)

        for route in expected_routes:
            route[Route.NEXT_HOP_INTERFACE] = "eth1"

        cur_state = libnmstate.show()
        assert_routes(expected_routes, cur_state)

    # https://issues.redhat.com/browse/RHEL-126481
    @pytest.mark.tier1
    @pytest.mark.parametrize(
        "desired_state_yaml",
        [
            """---
            interfaces:
            - name: eth1
              type: ethernet
              state: absent
            """,
            """---
            interfaces:
            - name: eth1
              type: ethernet
              state: absent
              alt-names:
              - name: port1
              - name: reallyreallylonglonglonginterfacenmae
            """,
        ],
        ids=["without_alt_names", "with_alt_names"],
    )
    def test_del_alt_name_of_absent_iface(
        self, eth1_with_alt_names, desired_state_yaml
    ):
        desired_state = load_yaml(desired_state_yaml)
        libnmstate.apply(desired_state)

        iface_state = show_only(("eth1",))[Interface.KEY][0]
        assert not iface_state.get(InterfaceAltName.KEY)

        # make sure systemd link file is also deleted
        retry_till_true_or_timeout(
            RETRY_TIMEOUT,
            udev_trigger_check_alt_names,
            "eth1",
            [],
        )

    # https://issues.redhat.com/browse/RHEL-126510
    @pytest.mark.tier1
    def test_ref_alt_name_as_interface_name(self, eth1_with_alt_names):
        desired_state = load_yaml(
            """---
                interfaces:
                - name: reallyreallylonglonglonginterfacenmae
                  type: ethernet
                  state: up
                  mtu: 1280
                """
        )
        libnmstate.apply(desired_state)

        iface_state = show_only(("eth1",))[Interface.KEY][0]
        assert iface_state[Interface.MTU] == 1280

    # https://issues.redhat.com/browse/RHEL-126510
    @pytest.mark.tier1
    def test_remove_interface_ref_by_alt_name(self, eth1_with_alt_names):
        desired_state = load_yaml(
            """---
                interfaces:
                - name: reallyreallylonglonglonginterfacenmae
                  type: ethernet
                  state: absent
                """
        )
        libnmstate.apply(desired_state)

        # Since we mark eth1 as absent, it should not hold any alt-names
        iface_state = show_only(("eth1",))[Interface.KEY][0]
        assert not iface_state.get(InterfaceAltName.KEY)

        # make sure systemd link file is also deleted
        retry_till_true_or_timeout(
            RETRY_TIMEOUT,
            udev_trigger_check_alt_names,
            "eth1",
            [],
        )

    @pytest.mark.parametrize(
        "desired_state_yaml",
        [
            """---
            interfaces:
            - name: reallyreallylonglonglonginterfacenmae
              type: ethernet
              state: absent
            - name: eth1
              type: ethernet
              state: up
            """,
            """---
            interfaces:
            - name: reallyreallylonglonglonginterfacenmae
              type: ethernet
              state: up
            - name: eth1
              type: ethernet
              state: absent
            """,
            """---
            interfaces:
            - name: reallyreallylonglonglonginterfacenmae
              type: ethernet
              state: up
            - name: eth1
              type: ethernet
              state: up
            """,
        ],
        ids=["absent_up", "up_absent", "up_up"],
    )
    def test_ref_alt_name_conflict_in_desire(
        self, eth1_with_alt_names, desired_state_yaml
    ):
        desired_state = load_yaml(desired_state_yaml)
        with pytest.raises(NmstateValueError):
            libnmstate.apply(desired_state)

    def test_both_alt_name_iface_and_kernel_iface_mark_as_absent(
        self, eth1_with_alt_names
    ):
        desired_state = load_yaml(
            """---
            interfaces:
            - name: reallyreallylonglonglonginterfacenmae
              type: ethernet
              state: absent
            - name: eth1
              type: ethernet
              state: absent
            """
        )
        libnmstate.apply(desired_state)

        # Since we mark eth1 as absent, it should not hold any alt-names
        iface_state = show_only(("eth1",))[Interface.KEY][0]
        assert not iface_state.get(InterfaceAltName.KEY)

        # make sure systemd link file is also deleted
        retry_till_true_or_timeout(
            RETRY_TIMEOUT,
            udev_trigger_check_alt_names,
            "eth1",
            [],
        )

    # https://redhat.atlassian.net/browse/RHEL-167955
    @pytest.mark.tier1
    def test_vlan_alt_name_uses_original_name_on_reapply(self, eth1_up):
        link_file = "/etc/systemd/network/98-nmstate-{}.link".format(
            TEST_VLAN_NIC
        )
        vlan_with_alt_name = load_yaml(
            """---
            interfaces:
            - name: {}
              type: vlan
              state: up
              vlan:
                base-iface: eth1
                id: 101
              alt-names:
              - name: my-vlan
            """.format(
                TEST_VLAN_NIC
            )
        )
        try:
            libnmstate.apply(vlan_with_alt_name)
            with open(link_file) as f:
                content = f.read()
            assert "OriginalName={}".format(TEST_VLAN_NIC) in content
            assert "MACAddress" not in content

            libnmstate.apply(vlan_with_alt_name)
            with open(link_file) as f:
                content = f.read()
            assert "OriginalName={}".format(TEST_VLAN_NIC) in content
            assert "MACAddress" not in content
        finally:
            libnmstate.apply(
                load_yaml(
                    """---
                    interfaces:
                    - name: {}
                      type: vlan
                      state: up
                      vlan:
                        base-iface: eth1
                        id: 101
                      alt-names:
                      - name: my-vlan
                        state: absent
                    """.format(
                        TEST_VLAN_NIC
                    )
                )
            )
            libnmstate.apply(
                load_yaml(
                    """---
                    interfaces:
                    - name: {}
                      type: vlan
                      state: absent
                    """.format(
                        TEST_VLAN_NIC
                    )
                )
            )

    # https://issues.redhat.com/browse/NMT-2202
    @pytest.mark.tier1
    def test_policy_capture_by_alt_name(self, eth1_with_alt_names):
        libnmstate.apply(
            load_yaml(
                """---
                interfaces:
                - name: eth1
                  type: ethernet
                  state: up
                  ipv4:
                    address:
                    - ip: 192.0.2.10
                      prefix-length: 24
                    dhcp: false
                    enabled: true
                """
            )
        )
        eth1_state = show_only(("eth1",))[Interface.KEY][0]
        eth1_mac = eth1_state["mac-address"]

        policy = load_yaml(
            """---
        capture:
          base-iface: interfaces.alt-names.name == "port1"
        desired:
          interfaces:
            - name: br0
              type: linux-bridge
              state: up
              mac-address: "{{ capture.base-iface.interfaces.0.mac-address }}"
              ipv4: "{{ capture.base-iface.interfaces.0.ipv4 }}"
              bridge:
                port:
                  - name: "{{ capture.base-iface.interfaces.0.name }}"
            """
        )
        cur_state = libnmstate.show()
        desired_state = libnmstate.gen_net_state_from_policy(policy, cur_state)

        with linux_bridge(TEST_BRIDGE_NIC, {}, create=False):
            libnmstate.apply(desired_state)

            br_state = show_only((TEST_BRIDGE_NIC,))[Interface.KEY][0]
            assert br_state["mac-address"] == eth1_mac
            assert state_match(
                [{"name": "eth1"}],
                br_state[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE],
            )

    # https://issues.redhat.com/browse/NMT-2202
    @pytest.mark.tier1
    def test_policy_capture_by_alt_name_bridge_port(self, eth1_with_alt_names):
        policy = load_yaml(
            """---
        capture:
          base-iface: >-
            interfaces.alt-names.name ==
            "reallyreallylonglonglonginterfacenmae"
        desired:
          interfaces:
            - name: br0
              type: linux-bridge
              state: up
              bridge:
                port:
                  - name: "{{ capture.base-iface.interfaces.0.name }}"
            """
        )
        cur_state = libnmstate.show()
        desired_state = libnmstate.gen_net_state_from_policy(policy, cur_state)

        with linux_bridge(TEST_BRIDGE_NIC, {}, create=False):
            libnmstate.apply(desired_state)

            br_state = show_only((TEST_BRIDGE_NIC,))[Interface.KEY][0]
            assert state_match(
                [{"name": "eth1"}],
                br_state[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE],
            )
