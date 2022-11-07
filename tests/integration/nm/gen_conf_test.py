#
# Copyright (c) 2022 Red Hat, Inc.
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

import time

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import RouteRule

from ..testlib.env import is_k8s
from ..testlib import iprule
from ..testlib.statelib import show_only
from ..testlib.genconf import gen_conf_apply


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
def test_gen_conf_routes_rules():
    desired_state = load_yaml(
        """
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
      table-id: 254
route-rules:
  config:
    - ip-to: 192.0.2.0/24
      ip-from: 192.168.2.0/24
      priority: 1
      route-table: 254
"""
    )
    with gen_conf_apply(desired_state):
        rule = desired_state[RouteRule.KEY][RouteRule.CONFIG][0]
        iprule.ip_rule_exist_in_os(
            rule.get(RouteRule.IP_FROM),
            rule.get(RouteRule.IP_TO),
            rule.get(RouteRule.PRIORITY),
            rule.get(RouteRule.ROUTE_TABLE),
            rule.get(RouteRule.FWMARK),
            rule.get(RouteRule.FWMASK),
            rule.get(RouteRule.FAMILY),
        )


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
