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

import uuid

from libnmstate import nmclient


def create_profile(settings):
    con_profile = nmclient.NM.SimpleConnection.new()
    for setting in settings:
        con_profile.add_setting(setting)

    return con_profile


def add_profile(connection_profile, save_to_disk=True):
    client = nmclient.client()
    client.add_connection_async(connection_profile, save_to_disk)


def update_profile(base_profile, new_profile):
    base_profile.replace_settings_from_connection(new_profile)


def commit_profile(connection_profile, save_to_disk=True):
    connection_profile.commit_changes_async(save_to_disk)


def create_setting(con_name, iface_name, iface_type):
    con_setting = nmclient.NM.SettingConnection.new()
    con_setting.props.id = con_name
    con_setting.props.interface_name = iface_name
    con_setting.props.uuid = str(uuid.uuid4())
    con_setting.props.type = iface_type
    con_setting.props.autoconnect = True
    con_setting.props.autoconnect_slaves = (
        nmclient.NM.SettingConnectionAutoconnectSlaves.NO)
    return con_setting


def duplicate_settings(base_connection_profile):
    base = base_connection_profile.get_setting_connection()
    new = nmclient.NM.SettingConnection.new()
    new.props.id = base.props.id
    new.props.interface_name = base.props.interface_name
    new.props.uuid = base.props.uuid
    new.props.type = base.props.type
    new.props.autoconnect = base.props.autoconnect
    new.props.autoconnect_slaves = base.props.autoconnect_slaves
    return new


def get_device_connection(nm_device):
    act_connection = nm_device.get_active_connection()
    if act_connection:
        return act_connection.props.connection
    return None
