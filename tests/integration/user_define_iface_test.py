# SPDX-License-Identifier: Apache-2.0

import libnmstate
from libnmstate.schema import UserDefined
from libnmstate.schema import Interface

import pytest

from .testlib import assertlib
from .testlib.yaml import load_yaml
from .testlib.env import nm_minor_version


@pytest.fixture(autouse=True)
def vxcan_cleanup():
    yield
    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: vxcan1
              type: vxcan
              state: absent
            user-defined:
              interface-types:
              - name: vxcan
                state: absent
            """
        )
    )
    cur_state = libnmstate.show()

    assert not cur_state.get(UserDefined.KEY)
    assert "vxcan1" not in [
        iface[Interface.NAME] for iface in cur_state[Interface.KEY]
    ]


@pytest.mark.xfail(
    nm_minor_version() < 46,
    reason="NetworkManager 1.46- does not support generic device handler",
)
def test_user_defined_iface_vxcan():
    desired_state = load_yaml(
        """---
    interfaces:
    - name: vxcan1
      description: user defined vxcan interface
      type: vxcan
      state: up
      ipv4:
        enabled: true
        address:
        - ip: 192.0.2.1
          prefix-length: 24
      ipv6:
        enabled: false
      user-defined:
        peer: vxcan1-ep
    user-defined:
      interface-types:
      - name: vxcan
        handler-script: |
          #!/bin/bash
          ifname=$1
          action=$2

          if [ "$action" = "device-add" ]; then
              peer=$CONNECTION_USER_VXCAN__PEER

              if [ -z "$peer" ]; then
                  echo "ERROR=Missing peer name"
                  exit 1
              fi

              if ! err=$(ip link add "$ifname" type vxcan peer "$peer" 2>&1);
              then
                  echo "ERROR=Failed creating the interface: $err"
                  exit 2
              fi
              ip link set $peer up

              echo IFINDEX="$(cat /sys/class/net/"$ifname"/ifindex)"
              exit 0
          elif [ "$action" = "device-delete" ]; then
              # Delete the interface created by "device-add" here.
              ip link del "$ifname"
              exit 0
          fi"""
    )
    libnmstate.apply(desired_state)

    # assert_state_match does not support the top `user-defined` section
    desired_state.pop("user-defined")

    assertlib.assert_state_match(desired_state)
