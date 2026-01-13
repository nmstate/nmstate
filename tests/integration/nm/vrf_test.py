# SPDX-License-Identifier: Apache-2.0

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import VRF

from ..testlib.statelib import show_only
from ..testlib.cmdlib import exec_cmd


@pytest.fixture
def vrf0_with_unmanaged_port_veth1():
    desired_state = yaml.load(
        """---
        interfaces:
        - name: vrf0
          type: vrf
          state: up
          vrf:
            port: []
            route-table-id: 100
        """,
        Loader=yaml.SafeLoader,
    )

    libnmstate.apply(desired_state)
    exec_cmd("ip link add veth1 type veth peer veth1_peer".split(), check=True)
    exec_cmd("nmcli d set veth1 managed false".split(), check=True)
    exec_cmd("nmcli d set veth1_peer managed false".split(), check=True)
    exec_cmd("ip link set veth1 master vrf0".split(), check=True)
    exec_cmd("ip link set veth1 up".split(), check=True)
    exec_cmd("ip link set veth1_peer up".split(), check=True)
    yield
    desired_state = yaml.load(
        """---
        interfaces:
        - name: vrf0
          type: vrf
          state: absent
          vrf:
            port: []
        """,
        Loader=yaml.SafeLoader,
    )

    libnmstate.apply(desired_state)
    exec_cmd("ip link del veth1".split(), check=True)


def test_vrf_apply_with_empty_port_list_and_unmanged_port(
    vrf0_with_unmanaged_port_veth1,
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: vrf0
          type: vrf
          state: up
          vrf:
            port: []
        """,
        Loader=yaml.SafeLoader,
    )

    libnmstate.apply(desired_state)

    iface_state = show_only(("vrf0",))[Interface.KEY][0]
    assert iface_state[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] == ["veth1"]
    iface_state = show_only(("veth1",))[Interface.KEY][0]
    assert iface_state[Interface.STATE] == InterfaceState.IGNORE


def test_vrf_take_over_unmanaged_port(vrf0_with_unmanaged_port_veth1):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: vrf0
          type: vrf
          state: up
          vrf:
            port:
            - veth1
        - name: veth1
          type: ethernet
          state: up
        """,
        Loader=yaml.SafeLoader,
    )

    libnmstate.apply(desired_state)

    iface_state = show_only(("vrf0",))[Interface.KEY][0]
    assert iface_state[VRF.CONFIG_SUBTREE][VRF.PORT_SUBTREE] == ["veth1"]

    iface_state = show_only(("veth1",))[Interface.KEY][0]
    assert iface_state[Interface.STATE] == InterfaceState.UP
