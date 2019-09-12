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

from contextlib import contextmanager

import libnmstate
from .statelib import INTERFACES


@contextmanager
def vlan_interface(ifname, vlan_id, base_iface, create=True):
    desired_state = {
        INTERFACES: [
            {
                'name': ifname,
                'type': 'vlan',
                'state': 'up',
                'vlan': {'id': vlan_id, 'base-iface': base_iface},
            }
        ]
    }

    if create:
        libnmstate.apply(desired_state)

    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {INTERFACES: [{'name': ifname, 'type': 'vlan', 'state': 'absent'}]}
        )
