#
# Copyright (c) 2019 Red Hat, Inc.
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

import yaml

import libnmstate
from libnmstate.schema import InterfaceIPv4

from .testlib import statelib
from .testlib.statelib import INTERFACES


OVS_BRIDGE_YAML_BASE = """
interfaces:
  - name: ovs-br0
    type: ovs-bridge
    state: up
    bridge:
      options:
        fail-mode: ''
        mcast-snooping-enable: false
        rstp: false
        stp: true
"""


def test_create_and_remove_ovs_bridge_with_a_system_port(eth1_up):
    state = yaml.load(OVS_BRIDGE_YAML_BASE, Loader=yaml.SafeLoader)
    state[INTERFACES][0]['bridge']['port'] = [
        {'name': 'eth1', 'type': 'system'}
    ]
    libnmstate.apply(state)

    setup_remove_ovs_bridge_state = {
        INTERFACES: [
            {'name': 'ovs-br0', 'type': 'ovs-bridge', 'state': 'absent'}
        ]
    }
    libnmstate.apply(setup_remove_ovs_bridge_state)
    state = statelib.show_only((state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_create_and_remove_ovs_bridge_with_min_desired_state():
    desired_state = {
        INTERFACES: [{'name': 'ovs-br0', 'type': 'ovs-bridge', 'state': 'up'}]
    }
    libnmstate.apply(desired_state)

    setup_remove_ovs_bridge_state = {
        INTERFACES: [
            {'name': 'ovs-br0', 'type': 'ovs-bridge', 'state': 'absent'}
        ]
    }
    libnmstate.apply(setup_remove_ovs_bridge_state)
    state = statelib.show_only((desired_state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_create_and_remove_ovs_bridge_with_an_internal_port():
    state = yaml.load(OVS_BRIDGE_YAML_BASE, Loader=yaml.SafeLoader)
    state[INTERFACES][0]['bridge']['port'] = [
        {'name': 'ovs0', 'type': 'internal'}
    ]
    ovs_internal_interface_state = {
        'name': 'ovs0',
        'type': 'ovs-interface',
        'state': 'up',
        'mtu': 1500,
        'ipv4': {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: '192.0.2.1',
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        },
    }
    state[INTERFACES].append(ovs_internal_interface_state)
    libnmstate.apply(state, verify_change=False)

    setup_remove_ovs_bridge_state_and_port = {
        INTERFACES: [
            {'name': 'ovs-br0', 'type': 'ovs-bridge', 'state': 'absent'},
            {'name': 'ovs', 'type': 'ovs-interface', 'state': 'absent'},
        ]
    }
    libnmstate.apply(setup_remove_ovs_bridge_state_and_port)
    state = statelib.show_only(
        (state[INTERFACES][0]['name'], state[INTERFACES][1]['name'])
    )
    assert not state[INTERFACES]
