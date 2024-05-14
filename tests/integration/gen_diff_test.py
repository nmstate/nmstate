# SPDX-License-Identifier: LGPL-2.1-or-later

import libnmstate

from .testlib.yaml import load_yaml


def test_gen_diff():
    des_state = load_yaml(
        """---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: true
            ipv6:
              enabled: false
            """
    )
    cur_state = load_yaml(
        """---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv4:
              enabled: true
              dhcp: true
              auto-dns: true
              auto-gateway: true
              auto-routes: true
              auto-route-table-id: 0
            ipv6:
              enabled: true
              dhcp: true
              autoconf: true
              auto-dns: true
              auto-gateway: true
              auto-routes: true
              auto-route-table-id: 0"""
    )
    expected_state = load_yaml(
        """---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            ipv6:
              enabled: false"""
    )

    assert (
        libnmstate.generate_differences(des_state, cur_state) == expected_state
    )
