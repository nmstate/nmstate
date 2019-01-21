#
# Copyright 2018-2019 Red Hat, Inc.
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

import logging
import uuid

from . import nmclient


def create_profile(settings):
    con_profile = nmclient.NM.SimpleConnection.new()
    for setting in settings:
        con_profile.add_setting(setting)

    return con_profile


def add_profile(connection_profile, save_to_disk=True):
    client = nmclient.client()
    mainloop = nmclient.mainloop()
    user_data = mainloop
    mainloop.push_action(
        client.add_connection_async,
        connection_profile,
        save_to_disk,
        mainloop.cancellable,
        _add_connection_callback,
        user_data,
    )


def _add_connection_callback(src_object, result, user_data):
    mainloop = user_data
    try:
        con = src_object.add_connection_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug(
                'Connection adding canceled: error=%s', e)
        else:
            mainloop.quit(
                'Connection adding failed: error={}'.format(e))
        return

    if con is None:
        mainloop.quit('Connection adding failed: error=unknown')
    else:
        devname = con.get_interface_name()
        logging.debug('Connection adding succeeded: dev=%s', devname)
        mainloop.execute_next_action()


def update_profile(base_profile, new_profile):
    base_profile.replace_settings_from_connection(new_profile)


def commit_profile(connection_profile, save_to_disk=True, nmdev=None):
    mainloop = nmclient.mainloop()
    user_data = mainloop, nmdev
    mainloop.push_action(
        connection_profile.commit_changes_async,
        save_to_disk,
        mainloop.cancellable,
        _commit_changes_callback,
        user_data,
    )


def _commit_changes_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.commit_changes_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection update aborted: error=%s', e)
        else:
            mainloop.quit(
                'Connection update failed: error={}, dev={}/{}'.format(
                    e, nmdev.props.interface, nmdev.props.state))
        return

    devname = src_object.get_interface_name()
    if success:
        logging.debug('Connection update succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit('Connection update failed: '
                      'dev={}, error=unknown'.format(devname))


def create_setting(con_name, iface_name, iface_type):
    con_setting = nmclient.NM.SettingConnection.new()
    con_setting.props.id = con_name
    con_setting.props.interface_name = iface_name
    con_setting.props.uuid = str(uuid.uuid4())
    con_setting.props.type = iface_type
    con_setting.props.autoconnect = True
    con_setting.props.autoconnect_slaves = (
        nmclient.NM.SettingConnectionAutoconnectSlaves.YES)
    _logging_connection_info(con_setting, 'create_setting')
    return con_setting


def duplicate_settings(base_connection_profile):
    base = base_connection_profile.get_setting_connection()
    new = nmclient.NM.SettingConnection.new()
    new.props.id = base.props.id
    new.props.interface_name = base.props.interface_name
    new.props.uuid = base.props.uuid
    new.props.type = base.props.type
    new.props.autoconnect = True
    new.props.autoconnect_slaves = base.props.autoconnect_slaves
    _logging_connection_info(new, 'duplicate_settings')
    return new


def set_master_setting(con_setting, master, slave_type):
    if master is not None:
        con_setting.props.master = master
        con_setting.props.slave_type = slave_type


def get_device_connection(nm_device):
    act_connection = get_device_active_connection(nm_device)
    if act_connection:
        return act_connection.props.connection
    return None


def get_device_active_connection(nm_device):
    active_conn = None
    if nm_device:
        active_conn = nm_device.get_active_connection()
    return active_conn


def get_connection_by_id(connection_id):
    client = nmclient.client()
    conn = None
    if connection_id:
        conn = client.get_connection_by_id(connection_id)
    return conn


def _logging_connection_info(con_setting, source):
    logging.debug(
        'Connection settings for %s:\n' +
        '\n'.join([
            'id: %s',
            'iface: %s',
            'uuid: %s',
            'type: %s',
            'autoconnect: %s',
            'autoconnect_slaves: %s'
        ]),
        source,
        con_setting.props.id,
        con_setting.props.interface_name,
        con_setting.props.uuid,
        con_setting.props.type,
        con_setting.props.autoconnect,
        con_setting.props.autoconnect_slaves
    )
