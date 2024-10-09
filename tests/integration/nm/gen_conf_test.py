# SPDX-License-Identifier: LGPL-2.1-or-later

import time

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


@pytest.mark.tier1
def test_gen_conf_routes_rules():
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


@pytest.mark.skipif(
    nm_minor_version() < 41, reason="ECMP route is only support on NM 1.41+"
)
def test_gen_conf_ecmp_routes():
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


def test_gen_conf_lldp():
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
