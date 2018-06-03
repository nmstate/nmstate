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

import six

from libnmstate import netinfo
from libnmstate import nm
from libnmstate import nmclient
from libnmstate import validator


class UnsupportedIfaceStateError(Exception):
    pass


def apply(desired_state):
    validator.verify(desired_state)

    interfaces_current_state = netinfo.interfaces()

    _apply_ifaces_state(desired_state['interfaces'], interfaces_current_state)


def _apply_ifaces_state(interfaces_desired_state, interfaces_current_state):
    client = nmclient.client(refresh=True)

    ifaces_desired_state = _index_by_name(interfaces_desired_state)
    ifaces_current_state = _index_by_name(interfaces_current_state)

    _add_interfaces(client, ifaces_desired_state, ifaces_current_state)
    _edit_interfaces(client, ifaces_desired_state, ifaces_current_state)


def _add_interfaces(client, ifaces_desired_state, ifaces_current_state):
    ifaces2add = [
        ifaces_desired_state[name] for name in
        six.viewkeys(ifaces_desired_state) - six.viewkeys(ifaces_current_state)
    ]
    new_con_profiles = [_build_connection_profile(iface_desired_state)
                        for iface_desired_state in ifaces2add]
    for connection_profile in new_con_profiles:
        client.add_connection_async(connection_profile, save_to_disk=True)


def _edit_interfaces(client, ifaces_desired_state, ifaces_current_state):
    ifaces2edit = [
        ifaces_desired_state[name] for name in
        six.viewkeys(ifaces_desired_state) & six.viewkeys(ifaces_current_state)
    ]
    for iface_desired_state in ifaces2edit:
        nmdev = client.get_device_by_iface(iface_desired_state['name'])
        if nmdev:
            _apply_iface_admin_state(client, iface_desired_state, nmdev)


def _apply_iface_admin_state(client, iface_state, nmdev):
    if iface_state['state'] == 'up':
        if nmdev.get_state() != nmclient.NM.DeviceState.ACTIVATED:
            client.activate_connection_async(device=nmdev)
    elif iface_state['state'] == 'down':
        active_connection = nmdev.get_active_connection()
        if active_connection:
            client.deactivate_connection_async(active_connection)
    elif iface_state['state'] == 'absent':
        connections = nmdev.get_available_connections()
        for con in connections:
            con.delete_async()
    else:
        raise UnsupportedIfaceStateError(iface_state)


def _index_by_name(ifaces_state):
    return {iface['name']: iface for iface in ifaces_state}


def _build_connection_profile(iface_desired_state):
    iface_type = nm.translator.api2nm_iface_type(iface_desired_state['type'])
    settings = [
        nm.connection.create_setting(
            con_name=iface_desired_state['name'],
            iface_name=iface_desired_state['name'],
            iface_type=iface_type,
        ),
        nm.ipv4.create_setting(),
        nm.ipv6.create_setting(),
    ]
    if iface_type == 'bond':
        bond_conf = iface_desired_state['link-aggregation']
        bond_opts = nm.translator.api2nm_bond_options(bond_conf)

        settings.append(nm.bond.create_setting(bond_opts))

    return nm.connection.create_profile(settings)
