# SPDX-License-Identifier: Apache-2.0

import libnmstate

from .testlib.yaml import load_yaml


def test_pretty_state_yaml():
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

    assert "- name: eth1" in libnmstate.PrettyState(state).yaml


def test_pretty_state_json():
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

    assert '[{"name":"eth1"' in libnmstate.PrettyState(state).json
