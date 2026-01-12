# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate

from ..testlib.yaml import load_yaml
from ..testlib.cmdlib import exec_cmd


HSR_NIC = "hsr0"


@pytest.fixture
def eth1_up_with_auto_ip(eth1_up):
    state = load_yaml(
        """---
    interfaces:
      - name: eth1
        type: ethernet
        state: up
        ipv4:
          enabled: true
          dhcp: true
        ipv6:
          enabled: true
          dhcp: true
          autoconf: true"""
    )

    libnmstate.apply(state)
    yield


@pytest.fixture
def clean_up():
    yield
    state = load_yaml(
        f"""---
            interfaces:
            - name: {HSR_NIC}
              type: hsr
              state: absent
        """
    )
    libnmstate.apply(state)


def test_auto_disable_ip_of_hsr_ports(eth1_up_with_auto_ip, eth1_up, clean_up):
    state = load_yaml(
        """---
            interfaces:
              - name: hsr0
                type: hsr
                state: up
                copy-mac-from: eth1
                hsr:
                  port1: eth1
                  port2: eth2
                  multicast-spec: 40
                  protocol: prp
            """
    )
    libnmstate.apply(state)

    assert (
        exec_cmd("nmcli -g ipv4.method c show eth1".split(), check=True)[1]
        == "disabled\n"
    )
    assert (
        exec_cmd("nmcli -g ipv6.method c show eth1".split(), check=True)[1]
        == "disabled\n"
    )

    assert (
        exec_cmd("nmcli -g ipv4.method c show eth2".split(), check=True)[1]
        == "disabled\n"
    )
    assert (
        exec_cmd("nmcli -g ipv6.method c show eth2".split(), check=True)[1]
        == "disabled\n"
    )
