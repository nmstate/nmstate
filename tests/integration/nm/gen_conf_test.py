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

import os
import time

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge

from ..testlib.nmplugin import nm_service_restart
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
    result = libnmstate.generate_configurations(desired_state)[
        "NetworkManager"
    ]
    with nm_service_restart():
        for file_name, file_content in result:
            save_nm_config(file_name, file_content)

    retry_verify_ovs_ports("br0", sorted(["eth1", "br0"]))


def save_nm_config(file_name, file_content):
    file_path = f"{NM_CONFIG_FOLDER}/{file_name}"
    with open(file_path, "w") as fd:
        fd.write(file_content)
    os.chown(file_path, 0, 0)
    os.chmod(file_path, 0o600)


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
        for p in cur_iface.get(OVSBridge.CONFIG_SUBTREE, {}).get(
            OVSBridge.PORT_SUBTREE, []
        )
    ]
    cur_ports.sort()
    assert cur_ports == port_names
