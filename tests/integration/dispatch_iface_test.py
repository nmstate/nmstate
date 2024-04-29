# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Dispatch
from libnmstate.schema import DispatchInterfaceType
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4

from .testlib import assertlib
from .testlib.env import nm_minor_version
from .testlib.yaml import load_yaml
from .testlib.statelib import show_only

TEST_NIC1 = "vxcan1"
TEST_NIC2 = "vxcan2"


@pytest.fixture
def vxcan_cleanup():
    yield
    libnmstate.apply(
        load_yaml(
            f"""---
            interfaces:
            - name: {TEST_NIC1}
              type: dispatch
              state: absent
            - name: {TEST_NIC2}
              type: dispatch
              state: absent
            dispatch:
              interfaces:
              - type: vxcan
                state: absent
            """
        )
    )
    cur_state = libnmstate.show()

    assert not cur_state.get(Dispatch.KEY)
    assert TEST_NIC1 not in [
        iface[Interface.NAME] for iface in cur_state[Interface.KEY]
    ]
    assert TEST_NIC2 not in [
        iface[Interface.NAME] for iface in cur_state[Interface.KEY]
    ]


@pytest.fixture
def vxcan1_dispatch_iface(vxcan_cleanup):
    desired_state = load_yaml(
        """---
        dispatch:
          interfaces:
          - type: vxcan
            activation: ip link add $name type vxcan peer $peer
            deactivation: ip link del $name
            kernel-index-getter: cat /sys/class/net/$name/ifindex
            allowed-variable-names:
            - peer
        interfaces:
        - name: vxcan1
          type: dispatch
          state: up
          ipv4:
            enabled: true
            address:
            - ip: 192.0.2.1
              prefix-length: 24
          dispatch:
            type: vxcan
            variables:
              peer: vxcan1-ep
          """
    )
    libnmstate.apply(desired_state)
    yield desired_state


@pytest.mark.xfail(
    nm_minor_version() < 46,
    reason="NetworkManager 1.46- does not support generic device handler",
)
def test_dispatch_iface_vxcan(vxcan1_dispatch_iface):
    desired_state = vxcan1_dispatch_iface

    assertlib.assert_state_match(desired_state)

    state = libnmstate.show()
    assert state[Dispatch.KEY] == desired_state[Dispatch.KEY]


@pytest.mark.xfail(
    nm_minor_version() < 46,
    reason="NetworkManager 1.46- does not support generic device handler",
)
def test_add_dispatch_to_existing_dispatch_interface_type(
    vxcan1_dispatch_iface,
):
    libnmstate.apply(
        load_yaml(
            f"""---
        interfaces:
        - name: {TEST_NIC2}
          type: dispatch
          state: up
          ipv4:
            enabled: true
            address:
            - ip: 192.0.2.2
              prefix-length: 24
          dispatch:
            type: vxcan
            variables:
              peer: vxcan2-ep
        """
        )
    )

    iface_state = show_only((TEST_NIC2,))[Interface.KEY][0]
    assert iface_state[Interface.IPV4][InterfaceIPv4.ADDRESS] == [
        {
            InterfaceIPv4.ADDRESS_IP: "192.0.2.2",
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
        }
    ]


@pytest.mark.xfail(
    nm_minor_version() < 46,
    reason="NetworkManager 1.46- does not support generic device handler",
)
def test_not_allowing_remove_dispatch_interface_type_with_iface_exist(
    vxcan1_dispatch_iface,
):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            load_yaml(
                """---
            dispatch:
              interfaces:
              - type: vxcan
                state: absent
            """
            )
        )


@pytest.mark.xfail(
    nm_minor_version() < 46,
    reason="NetworkManager 1.46- does not support generic device handler",
)
def test_purging_dispatch_interface_types(
    vxcan1_dispatch_iface,
):
    libnmstate.apply(
        load_yaml(
            f"""---
            dispatch:
              interfaces: []
            interfaces:
              - name: {TEST_NIC1}
                type: dispatch
                state: absent
            """
        )
    )

    assert not show_only((TEST_NIC1,))[Interface.KEY]
    assert Dispatch.KEY not in libnmstate.show()
