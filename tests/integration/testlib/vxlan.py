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

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import VXLAN


class VxlanState:
    def __init__(self, id, base_if, remote, destination_port=4789):
        self.name = f"{base_if}.{id}"
        self.id = id
        self.base_if = base_if
        self.remote = remote
        self.destination_port = destination_port

    @property
    def up(self):
        return {
            Interface.NAME: self.name,
            Interface.TYPE: VXLAN.TYPE,
            Interface.STATE: InterfaceState.UP,
            VXLAN.CONFIG_SUBTREE: {
                VXLAN.ID: self.id,
                VXLAN.BASE_IFACE: self.base_if,
                VXLAN.REMOTE: self.remote,
                VXLAN.DESTINATION_PORT: self.destination_port,
            },
        }

    @property
    def absent(self):
        return {
            Interface.NAME: self.name,
            Interface.TYPE: VXLAN.TYPE,
            Interface.STATE: InterfaceState.ABSENT,
        }

    @property
    def down(self):
        return {
            Interface.NAME: self.name,
            Interface.TYPE: VXLAN.TYPE,
            Interface.STATE: InterfaceState.DOWN,
        }


@contextmanager
def vxlan_interfaces(*vxlans, create=True):
    setup_state = vxlans_up(vxlans)
    if create:
        libnmstate.apply(setup_state)
    try:
        yield setup_state
    finally:
        libnmstate.apply(vxlans_absent(vxlans))


def vxlans_up(vxlans):
    vxlans_state = [vxlan_state.up for vxlan_state in vxlans]
    return {Interface.KEY: vxlans_state}


def vxlans_absent(vxlans):
    vxlans_state = [vxlan_state.absent for vxlan_state in vxlans]
    return {Interface.KEY: vxlans_state}


def vxlans_down(vxlans):
    vxlans_state = [vxlan_state.down for vxlan_state in vxlans]
    return {Interface.KEY: vxlans_state}
