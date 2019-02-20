#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import yaml

from libnmstate import netapplier

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
      port:
        - name: eth1
          type: system
"""


def test_create_and_remove_ovs_bridge_with_a_system_port(eth1_up):
    state = yaml.load(OVS_BRIDGE_YAML_BASE)
    netapplier.apply(state)

    setup_remove_ovs_bridge_state = {
        INTERFACES: [
            {
                'name': 'ovs-br0',
                'type': 'ovs-bridge',
                'state': 'absent'
            }
        ]
    }
    netapplier.apply(setup_remove_ovs_bridge_state)
    state = statelib.show_only((state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_create_and_remove_ovs_bridge_with_min_desired_state(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'ovs-br0',
                'type': 'ovs-bridge',
                'state': 'up'
            }
        ]
    }
    netapplier.apply(desired_state)

    setup_remove_ovs_bridge_state = {
        INTERFACES: [
            {
                'name': 'ovs-br0',
                'type': 'ovs-bridge',
                'state': 'absent'
            }
        ]
    }
    netapplier.apply(setup_remove_ovs_bridge_state)
    state = statelib.show_only((desired_state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]
