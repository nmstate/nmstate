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


LINUX_BRIDGE_YAML_BASE = """
interfaces:
  - name: linux-br0
    type: linux-bridge
    state: up
    bridge:
      options:
        group-forward-mask: 0
        mac-ageing-time: 300
        multicast-snooping: true
        stp:
          enabled: true
          forward-delay: 15
          hello-time: 2
          max-age: 20
          priority: 32768
      port:
        - name: eth1
          stp-hairpin-mode: false
          stp-path-cost: 100
          stp-priority: 32
"""


def test_create_and_remove_linux_bridge(eth1_up):
    state = yaml.load(LINUX_BRIDGE_YAML_BASE)
    netapplier.apply(state)

    setup_remove_linux_bridge_state = {
        INTERFACES: [
            {
                'name': 'linux-br0',
                'type': 'linux-bridge',
                'state': 'absent'
            }
        ]
    }
    netapplier.apply(setup_remove_linux_bridge_state)
    state = statelib.show_only((state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]


def test_create_and_remove_linux_bridge_with_min_desired_state(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'linux-br0',
                'type': 'linux-bridge',
                'state': 'up'
            }
        ]
    }
    netapplier.apply(desired_state)

    setup_remove_linux_bridge_state = {
        INTERFACES: [
            {
                'name': 'linux-br0',
                'type': 'linux-bridge',
                'state': 'absent'
            }
        ]
    }
    netapplier.apply(setup_remove_linux_bridge_state)
    state = statelib.show_only((desired_state[INTERFACES][0]['name'],))
    assert not state[INTERFACES]
