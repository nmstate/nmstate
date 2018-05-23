#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from libnmstate import nmclient
from libnmstate import validator


def apply(desired_state):
    validator.verify(desired_state)

    _apply_ifaces_state(desired_state)


def _apply_ifaces_state(state):
    client = nmclient.client()

    for iface_state in state['interfaces']:
        nmdev = client.get_device_by_iface(iface_state['name'])
        if iface_state['state'] == 'up':
            if nmdev.get_state() == nmclient.NM.DeviceState.ACTIVATED:
                continue
            client.activate_connection_async(device=nmdev)
        elif iface_state['state'] == 'down':
            active_connection = nmdev.get_active_connection()
            if active_connection:
                client.deactivate_connection_async(active_connection)
        else:
            raise UnsupportedIfaceStateError(iface_state)


class UnsupportedIfaceStateError(Exception):
    pass
