#
# Copyright 2018 Red Hat, Inc.
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

from . import bond
from . import connection
from . import device
from . import ipv4
from . import ipv6
from . import translator


class UnsupportedIfaceStateError(Exception):
    pass


def create_new_ifaces(con_profiles):
    for connection_profile in con_profiles:
        connection.add_profile(connection_profile, save_to_disk=True)


def prepare_new_ifaces_configuration(ifaces_desired_state):
    new_con_profiles = [
        _build_connection_profile(iface_desired_state)
        for iface_desired_state in ifaces_desired_state
    ]
    return new_con_profiles


def edit_existing_ifaces(con_profiles):
    for connection_profile in con_profiles:
        devname = connection_profile.get_interface_name()
        nmdev = device.get_device_by_name(devname)
        if nmdev:
            cur_con_profile = connection.get_device_connection(nmdev)
            if cur_con_profile:
                connection.commit_profile(connection_profile)
            else:
                # Missing connection, attempting to create a new one.
                connection.add_profile(connection_profile, save_to_disk=True)


def prepare_edited_ifaces_configuration(ifaces_desired_state):
    con_profiles = []
    for iface_desired_state in ifaces_desired_state:
        nmdev = device.get_device_by_name(iface_desired_state['name'])
        if nmdev:
            cur_con_profile = connection.get_device_connection(nmdev)
            new_con_profile = _build_connection_profile(
                iface_desired_state, base_con_profile=cur_con_profile)
            if cur_con_profile:
                connection.update_profile(cur_con_profile, new_con_profile)
                con_profiles.append(cur_con_profile)
            else:
                # Missing connection, attempting to create a new one.
                con_profiles.append(new_con_profile)

    return con_profiles


def set_ifaces_admin_state(ifaces_desired_state):
    for iface_desired_state in ifaces_desired_state:
        nmdev = device.get_device_by_name(iface_desired_state['name'])
        if nmdev:
            if iface_desired_state['state'] == 'up':
                device.activate(nmdev)
            elif iface_desired_state['state'] == 'down':
                device.deactivate(nmdev)
            elif iface_desired_state['state'] == 'absent':
                device.delete(nmdev)
            else:
                raise UnsupportedIfaceStateError(iface_desired_state)


def _build_connection_profile(iface_desired_state, base_con_profile=None):
    iface_type = translator.Api2Nm.get_iface_type(iface_desired_state['type'])

    settings = [
        ipv4.create_setting(iface_desired_state.get('ipv4')),
        ipv6.create_setting(),
    ]
    if base_con_profile:
        con_setting = connection.duplicate_settings(base_con_profile)
    else:
        con_setting = connection.create_setting(
            con_name=iface_desired_state['name'],
            iface_name=iface_desired_state['name'],
            iface_type=iface_type,
        )
    master = iface_desired_state.get('_master')
    connection.set_master_setting(con_setting, master, 'bond')
    settings.append(con_setting)

    bond_opts = translator.Api2Nm.get_bond_options(iface_desired_state)
    if bond_opts:
        settings.append(bond.create_setting(bond_opts))

    return connection.create_profile(settings)
