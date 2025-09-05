# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate

from .testlib.yaml import load_yaml


def test_validate_without_current():
    state = load_yaml(
        """---
        interfaces:
          - type: ethernet
            name: eth1
            ipv6:
              enabled: false
            state: up
            """
    )

    libnmstate.validate(state)


def test_validate_with_current():
    state = load_yaml(
        """---
        interfaces:
          - type: ethernet
            name: eth1
            ipv6:
              enabled: false
            state: up
        """
    )
    current = load_yaml(
        """---
        interfaces:
          - type: ethernet
            name: eth1
            ipv6:
              enabled: false
            state: up
        """
    )

    libnmstate.validate(state, current)


def test_validate_overbook():
    state = load_yaml(
        """---
        interfaces:
        - name: bond0
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            port:
            - eth2
            - eth1
        - name: bond1
          type: bond
          state: up
          link-aggregation:
            mode: balance-rr
            port:
            - eth2
            - eth3
        """
    )

    with pytest.raises(libnmstate.error.NmstateValueError):
        libnmstate.validate(state)


def test_validate_policy_bad_schema():
    state = load_yaml(
        """---
        capture:
          base-iface: interfaces.name |
        desired:
          interfaces:
          - name: "{{ capture.base-iface.interface.0.name }}"
        """
    )
    with pytest.raises(libnmstate.error.NmstateValueError):
        libnmstate.validate(state)


def test_validate_correct_policy_with_current():
    state = load_yaml(
        """---
        capture:
          ethernets: interfaces.type=="ethernet"
          ethernets-up: capture.ethernets | interfaces.state=="up"
          ethernets-lldp: capture.ethernets-up | interfaces.lldp.enabled:=true
          ethernets-lldp-skip-eth-conf: >-
            capture.ethernets-lldp | interfaces.ethernet := null
        desired:
          interfaces: '{{ capture.ethernets-lldp-skip-eth-conf.interfaces }}'
        """
    )
    current = load_yaml(
        """---
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            lldp:
              enabled: false
            """
    )
    libnmstate.validate(state, current)


def test_validate_correct_policy_without_current():
    state = load_yaml(
        """---
        capture:
          ethernets: interfaces.type=="ethernet"
          ethernets-up: capture.ethernets | interfaces.state=="up"
          ethernets-lldp: capture.ethernets-up | interfaces.lldp.enabled:=true
          ethernets-lldp-skip-eth-conf: >-
            capture.ethernets-lldp | interfaces.ethernet := null
        desiredState:
          interfaces: '{{ capture.ethernets-lldp-skip-eth-conf.interfaces }}'
        """
    )
    libnmstate.validate(state)
