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

from . import connection
from . import nmclient


def activate(dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    conn = connection.ConnectionProfile()
    conn.activate(dev, connection_id)


def deactivate(dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_deactivate_async, dev)


def _safe_deactivate_async(dev):
    act_connection = dev.get_active_connection()
    mainloop = nmclient.mainloop()
    if not act_connection or act_connection.props.state in (
            nmclient.NM.ActiveConnectionState.DEACTIVATING,
            nmclient.NM.ActiveConnectionState.DEACTIVATED):
        # Nothing left to do here, call the next action.
        mainloop.execute_next_action()
        return

    user_data = mainloop, dev
    client = nmclient.client()
    client.deactivate_connection_async(
        act_connection,
        mainloop.cancellable,
        _deactivate_connection_callback,
        user_data,
    )


def _deactivate_connection_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.deactivate_connection_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection deactivation aborted on %s: error=%s',
                          nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Connection deactivation failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    if success:
        logging.debug(
            'Connection deactivation succeeded on %s', nmdev.get_iface())
        mainloop.execute_next_action()
    else:
        mainloop.quit('Connection deactivation failed on %s: error=unknown' %
                      nmdev.get_iface())


def delete(dev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_async, dev)


# FIXME: Move the connection related functionality to the connection module.
def delete_connection(connection_id):
    mainloop = nmclient.mainloop()
    mainloop.push_action(
        _safe_delete_async, dev=None, connection_id=connection_id)


def _safe_delete_async(dev, connection_id=None):
    """Removes all device profiles."""
    if dev:
        connections = dev.get_available_connections()
        if not connections:
            conn = connection.ConnectionProfile()
            conn.import_by_id(dev.get_iface())
            if conn.profile:
                connections = [conn.profile]
    else:
        conn = connection.ConnectionProfile()
        conn.import_by_id(connection_id)
        connections = [conn.profile] if conn.profile else []
    mainloop = nmclient.mainloop()
    if not connections:
        # No callback is expected, so we should call the next one.
        mainloop.execute_next_action()
        return

    user_data = mainloop, dev
    for con in connections:
        con.delete_async(
            mainloop.cancellable,
            _delete_connection_callback,
            user_data,
        )


def _delete_connection_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.delete_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection deletion aborted on %s: error=%s',
                          nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Connection deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    devname = src_object.get_interface_name()
    if success:
        logging.debug('Connection deletion succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Connection deletion failed: '
            'dev={}, error=unknown'.format(devname))


def delete_device(nmdev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_device_async, nmdev)


def _safe_delete_device_async(nmdev):
    mainloop = nmclient.mainloop()
    if nmdev.get_state() == nmclient.NM.DeviceState.DEACTIVATING:
        # Nothing to do since the device is already being removed.
        mainloop.execute_next_action()
        return

    user_data = mainloop, nmdev
    nmdev.delete_async(
        mainloop.cancellable,
        _delete_device_callback,
        user_data,
    )


def _delete_device_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.delete_finish(result)
    # pylint: disable=catching-non-exception
    except nmclient.GLib.GError as e:
        # pylint: enable=catching-non-exception
        if e.matches(nmclient.Gio.DBusError.quark(),
                     nmclient.Gio.DBusError.UNKNOWN_METHOD):
            logging.debug('Device %s has been already deleted: error=%s',
                          nmdev.get_iface(), e)
            mainloop.execute_next_action()
        else:
            mainloop.quit(
                'Device deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Device deletion aborted on %s: error=%s',
                          nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Device deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    devname = src_object.get_iface()
    if success:
        logging.debug('Device deletion succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Device deletion failed: dev={}, error=unknown'.format(devname))


def get_device_by_name(devname):
    client = nmclient.client()
    return client.get_device_by_iface(devname)


def list_devices():
    client = nmclient.client()
    return client.get_devices()


def get_device_common_info(dev):
    return {
        'name': dev.get_iface(),
        'type_id': dev.get_device_type(),
        'type_name': dev.get_type_description(),
        'state': dev.get_state(),
    }
