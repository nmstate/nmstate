# SPDX-License-Identifier: Apache-2.0

import time
import os

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import Route
from libnmstate.schema import RouteRule
from libnmstate.schema import LLDP

from ..testlib import assertlib
from ..testlib import iprule
from ..testlib.env import is_k8s
from ..testlib.env import nm_minor_version
from ..testlib.genconf import gen_conf_apply
from ..testlib.ifacelib import get_mac_address
from ..testlib.route import assert_routes
from ..testlib.statelib import show_only

NM_CONFIG_FOLDER = "/etc/NetworkManager/system-connections"
MAX_RETRY_COUNT = 20


@pytest.fixture
def cleanup_ovs_same_name():
    yield
    libnmstate.apply(
        load_yaml(
            """
interfaces:
- name: br0
  type: ovs-bridge
  state: absent
"""
        ),
        verify_change=False,
    )


@pytest.mark.tier1
@pytest.mark.skipif(is_k8s(), reason="K8S does not support genconf")
def test_gen_conf_ovs_same_name(eth1_up, cleanup_ovs_same_name):
    desired_state = load_yaml(
        """
interfaces:
- name: eth1
  type: ethernet
  state: up
- name: br0
  type: ovs-bridge
  state: up
  bridge:
    port:
    - name: eth1
    - name: br0
- name: br0
  type: ovs-interface
  state: up
"""
    )

    with gen_conf_apply(desired_state):
        retry_verify_ovs_ports("br0", sorted(["eth1", "br0"]))


@pytest.mark.tier1
@pytest.mark.skipif(is_k8s(), reason="K8S does not support genconf")
def test_gen_conf_ovs_trunk_vlan():
    desired_state = load_yaml(
        """
interfaces:
  - name: ovs0
    type: ovs-interface
    state: up
  - name: ovs1
    type: ovs-interface
    state: up
  - name: ovs-br0
    type: ovs-bridge
    state: up
    bridge:
      port:
        - name: ovs0
          vlan:
            mode: access
            tag: 10
        - name: ovs1
          vlan:
            mode: trunk
            trunk-tags:
              - id: 1
              - id-range:
                  min: 10
                  max: 20
"""
    )

    with gen_conf_apply(desired_state):
        assertlib.assert_state_match(desired_state)


def test_gen_conf_mac_sec(eth1_eth2_up_with_no_config):
    desired_state = load_yaml(
        """
interfaces:
- name: eth1
  type: ethernet
- name: macsec0
  type: macsec
  state: up
  macsec:
    encrypt: true
    base-iface: eth1
    mka-cak: 50b71a8ef0bd5751ea76de6d6c98c03a
    mka-ckn: f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550
    port: 0
    validation: strict
    send-sci: true"""
    )

    with gen_conf_apply(desired_state):
        assertlib.assert_state_match(desired_state)


@pytest.mark.tier1
def test_gen_conf_routes_rules(eth1_up):
    desired_state = load_yaml(
        """---
        routes:
          config:
          - destination: 203.0.113.0/24
            metric: 108
            next-hop-address: 192.0.2.252
            next-hop-interface: eth1
            table-id: 200
          - destination: 2001:db8:a::/64
            metric: 108
            next-hop-address: 2001:db8:1::2
            next-hop-interface: eth1
            table-id: 200
        route-rules:
          config:
            - priority: 30001
              ip-from: 192.0.2.0/24
              suppress-prefix-length: 0
              route-table: 200
            - priority: 30002
              ip-from: 2001:db8:b::/64
              suppress-prefix-length: 1
              route-table: 200
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: false
              address:
              - ip: 192.0.2.251
                prefix-length: 24
            ipv6:
              enabled: true
              dhcp: false
              autoconf: false
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        """
    )
    with gen_conf_apply(desired_state):
        for rule in desired_state[RouteRule.KEY][RouteRule.CONFIG]:
            iprule.ip_rule_exist_in_os(rule)


def load_yaml(content):
    return yaml.load(content, Loader=yaml.SafeLoader)


# the assert_state_match does not works well on OVS same name
# manual checking
def retry_verify_ovs_ports(bridge_name, port_names):
    retry_count = 0
    while retry_count < MAX_RETRY_COUNT:
        try:
            verify_ovs_ports(bridge_name, port_names)
            break
        except AssertionError:
            retry_count += 1
            time.sleep(1)

    verify_ovs_ports(bridge_name, port_names)


def verify_ovs_ports(bridge_name, port_names):
    cur_iface = None
    for iface in show_only((bridge_name,))[Interface.KEY]:
        if iface[Interface.TYPE] == InterfaceType.OVS_BRIDGE:
            cur_iface = iface
            break
    assert cur_iface

    cur_ports = [
        p[OVSBridge.Port.NAME]
        for p in cur_iface[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE]
    ]
    cur_ports.sort()
    assert cur_ports == port_names


def test_gen_conf_ecmp_routes(eth1_up):
    desired_state = load_yaml(
        """---
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

        routes:
          config:
          - destination: 198.51.100.0/24
            metric: 150
            next-hop-address: 192.0.2.1
            next-hop-interface: eth1
            weight: 1
            table-id: 254
          - destination: 198.51.100.0/24
            metric: 150
            next-hop-address: 192.0.2.2
            next-hop-interface: eth1
            weight: 256
            table-id: 254
        """
    )
    with gen_conf_apply(desired_state):
        desired_routes = desired_state[Route.KEY][Route.CONFIG]
        cur_state = libnmstate.show()
        assert_routes(desired_routes, cur_state)


def test_gen_conf_lldp(eth1_up):
    desired_state = load_yaml(
        """---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            lldp:
              enabled: true
        """
    )
    with gen_conf_apply(desired_state):
        cur_state = show_only(["eth1"])
        assert cur_state[Interface.KEY][0][LLDP.CONFIG_SUBTREE][LLDP.ENABLED]

    desired_state[Interface.KEY][0][LLDP.CONFIG_SUBTREE][LLDP.ENABLED] = False
    with gen_conf_apply(desired_state):
        cur_state = show_only(["eth1"])
        assert not cur_state[Interface.KEY][0][LLDP.CONFIG_SUBTREE][
            LLDP.ENABLED
        ]


@pytest.mark.tier1
@pytest.mark.skipif(is_k8s(), reason="K8S does not support genconf")
def test_gen_conf_blackhole_routes():
    desired_state = load_yaml(
        """---
        routes:
          config:
            - destination: 198.51.200.0/24
              route-type: blackhole
            - destination: 2001:db8:f::/64
              route-type: blackhole
        """
    )
    with gen_conf_apply(desired_state):
        desired_routes = desired_state[Route.KEY][Route.CONFIG]
        # Linux kernel will automatically set next-hop-interface to lo for IPv6
        # blackhole routes.
        desired_routes[1][Route.NEXT_HOP_INTERFACE] = "lo"
        cur_state = libnmstate.show()
        assert_routes(desired_routes, cur_state, nic=None)


@pytest.fixture
def eth1_eth2_up_with_no_config(eth1_up, eth2_up):
    # Remove eth1 and eth2 config to make sure newly created one been activated
    # on next NM service reload

    libnmstate.apply(
        load_yaml(
            """
            interfaces:
            - name: eth1
              type: ethernet
              state: absent
            - name: eth2
              type: ethernet
              state: absent
            """
        )
    )


def test_gen_conf_bond_port_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")
    port2_mac = get_mac_address("eth2")

    desired_state = load_yaml(
        """---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: port2
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: bond0
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            port:
            - port1
            - port2""".format(
            port1_mac, port2_mac
        )
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: bond0
              type: bond
              state: up
              link-aggregation:
                mode: balance-rr
                port:
                - eth1
                - eth2"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_linux_bridge_port_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")
    port2_mac = get_mac_address("eth2")

    desired_state = load_yaml(
        """---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: port2
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: br0
          type: linux-bridge
          state: up
          bridge:
            port:
            - name: port1
            - name: port2""".format(
            port1_mac, port2_mac
        )
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: br0
              type: linux-bridge
              state: up
              bridge:
                port:
                - name: eth1
                - name: eth2"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_vrf_port_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")
    port2_mac = get_mac_address("eth2")

    desired_state = load_yaml(
        """---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: port2
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: vrf0
          type: vrf
          state: up
          vrf:
            route-table-id: 100
            port:
            - port1
            - port2""".format(
            port1_mac, port2_mac
        )
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: vrf0
              type: vrf
              state: up
              vrf:
                route-table-id: 100
                port:
                - eth1
                - eth2"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_route_next_hop_iface_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")

    desired_state = load_yaml(
        """---
        interfaces:
          - name: port1
            type: ethernet
            state: up
            mac-address: {}
            identifier: mac-address
            ipv4:
              enabled: true
              address:
              - ip: 192.0.2.251
                prefix-length: 24
              dhcp: false
        routes:
          config:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: port1
            """.format(
            port1_mac
        )
    )

    with gen_conf_apply(desired_state):
        expected_routes = load_yaml(
            """---
              - destination: 0.0.0.0/0
                next-hop-address: 192.0.2.1
                next-hop-interface: eth1"""
        )
        cur_state = libnmstate.show()
        assert_routes(expected_routes, cur_state)


def test_gen_conf_route_initcwnd_mtu_quickack_advmss_lock_mtu(eth1_up):
    desired_state = load_yaml(
        """---
        routes:
          config:
              - destination: 203.0.113.0/24
                mtu: 1550
                lock-mtu: true
                advmss: 1200
                next-hop-address: 192.0.2.252
                next-hop-interface: eth1
                table-id: 200
                initcwnd: 20
                initrwnd: 30
                quickack: true
              - destination: 2001:db8:a::/64
                mtu: 1280
                lock-mtu: true
                advmss: 1300
                next-hop-address: 2001:db8:1::2
                next-hop-interface: eth1
                table-id: 200
                initcwnd: 40
                initrwnd: 50
                quickack: false
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: false
              address:
              - ip: 192.0.2.251
                prefix-length: 24
            ipv6:
              enabled: true
              dhcp: false
              autoconf: false
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: false
              address:
              - ip: 192.0.2.251
                prefix-length: 24
            ipv6:
              enabled: true
              dhcp: false
              autoconf: false
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        """
    )
    with gen_conf_apply(desired_state):
        desired_routes = desired_state[Route.KEY][Route.CONFIG]
        cur_state = libnmstate.show()
        assert_routes(desired_routes, cur_state, nic=None)


@pytest.mark.skipif(
    nm_minor_version() < 48,
    reason="NetworkManager only fixed "
    "https://issues.redhat.com/browse/RHEL-34617 on 1.48+",
)
def test_gen_conf_ovs_bridge_port_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")
    port2_mac = get_mac_address("eth2")

    desired_state = load_yaml(
        """---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: port2
          type: ethernet
          identifier: mac-address
          mac-address: {}
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: port1
            - name: port2""".format(
            port1_mac, port2_mac
        )
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: br0
              type: ovs-bridge
              state: up
              bridge:
                port:
                - name: eth1
                - name: eth2"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_vlan_parent_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")

    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {port1_mac}
        - name: vlan100
          type: vlan
          state: up
          vlan:
            id: 100
            base-iface: port1
            """
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: vlan100
              type: vlan
              state: up
              vlan:
                id: 100
                base-iface: eth1"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_vxlan_parent_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")

    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {port1_mac}
        - name: vxlan100
          type: vxlan
          state: up
          vxlan:
            id: 100
            base-iface: port1
            """
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: vxlan100
              type: vxlan
              state: up
              vxlan:
                id: 100
                base-iface: eth1"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_macvlan_parent_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")

    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {port1_mac}
        - name: macvlan100
          type: mac-vlan
          state: up
          mac-vlan:
            base-iface: port1
            mode: passthru
            promiscuous: true
            """
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: macvlan100
              type: mac-vlan
              state: up
              mac-vlan:
                base-iface: eth1
                mode: passthru
                promiscuous: true"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_macvtap_parent_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")

    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {port1_mac}
        - name: macvtap100
          type: mac-vtap
          state: up
          mac-vtap:
            base-iface: port1
            mode: passthru
            promiscuous: true
            """
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: macvtap100
              type: mac-vtap
              state: up
              mac-vtap:
                base-iface: eth1
                mode: passthru
                promiscuous: true"""
        )
        assertlib.assert_state_match(expected_state)


def test_gen_conf_macsec_parent_ref_by_mac(eth1_eth2_up_with_no_config):
    port1_mac = get_mac_address("eth1")

    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: port1
          type: ethernet
          identifier: mac-address
          mac-address: {port1_mac}
        - name: macsec100
          type: macsec
          state: up
          macsec:
            encrypt: true
            base-iface: port1
            mka-cak: 50b71a8ef0bd5751ea76de6d6c98c03a
            mka-ckn: f2b4297d39da7330910a74abc0449feb
            port: 0
            validation: strict
            send-sci: true"""
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            """---
            interfaces:
            - name: macsec100
              type: macsec
              state: up
              macsec:
                encrypt: true
                base-iface: eth1
                mka-cak: 50b71a8ef0bd5751ea76de6d6c98c03a
                mka-ckn: f2b4297d39da7330910a74abc0449feb
                port: 0
                validation: strict
                send-sci: true"""
        )
        assertlib.assert_state_match(expected_state)


def _test_nic_name():
    return os.environ["TEST_REAL_NIC"]


def _test_nic_pci():
    iface_name = _test_nic_name()
    iface_state = show_only((iface_name,))[Interface.KEY][0]
    return iface_state[Interface.PCI]


@pytest.fixture
def real_nic_without_nm_connection():
    libnmstate.apply(
        load_yaml(
            f"""
            interfaces:
            - name: {_test_nic_name()}
              type: ethernet
              state: absent
            """
        )
    )


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for PCI identifier test",
)
def test_ref_vlan_parent_via_pci_address(real_nic_without_nm_connection):
    iface_name = _test_nic_name()
    pci_address = _test_nic_pci()

    desired_state = load_yaml(
        f"""---
        interfaces:
        - name: port1
          type: ethernet
          identifier: pci-address
          pci-address: "{pci_address}"
        - name: vlan100
          type: vlan
          state: up
          vlan:
            id: 100
            base-iface: port1
            """
    )

    with gen_conf_apply(desired_state):
        expected_state = load_yaml(
            f"""---
            interfaces:
            - name: vlan100
              type: vlan
              state: up
              vlan:
                id: 100
                base-iface: {iface_name}"""
        )
        assertlib.assert_state_match(expected_state)
