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

import logging

from libnmstate import nmclient


def activate(dev):
    client = nmclient.client()
    mainloop = nmclient.mainloop()
    connection = specific_object = None
    user_data = mainloop
    mainloop.push_action(
        client.activate_connection_async,
        connection,
        dev,
        specific_object,
        mainloop.cancellable,
        _active_connection_callback,
        user_data,
    )


def _active_connection_callback(src_object, result, user_data):
    mainloop = user_data
    try:
        act_con = src_object.activate_connection_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug(
                'Connection activation canceled: error=%s', e)
        else:
            mainloop.quit('Connection activation failed: error={}'.format(e))
        return

    if act_con is None:
        mainloop.quit('Connection activation failed: error=unknown')
    else:
        devname = act_con.props.connection.get_interface_name()
        logging.debug('Connection activation succeeded: dev=%s', devname)
        mainloop.execute_next_action()


def deactivate(dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    client = nmclient.client()
    act_connection = dev.get_active_connection()
    if act_connection:
        mainloop = nmclient.mainloop()
        user_data = mainloop
        mainloop.push_action(
            client.deactivate_connection_async,
            act_connection,
            mainloop.cancellable,
            _deactivate_connection_callback,
            user_data,
        )


def _deactivate_connection_callback(src_object, result, user_data):
    mainloop = user_data
    try:
        success = src_object.deactivate_connection_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection deactivation aborted: error=%s', e)
        else:
            mainloop.quit('Connection deactivation failed: error={}'.format(e))
        return

    if success:
        logging.debug('Connection deactivation succeeded')
        mainloop.execute_next_action()
    else:
        mainloop.quit('Connection deactivation failed: error=unknown')


def delete(dev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_async, dev)


def _safe_delete_async(dev):
    """Removes all device profiles."""
    connections = dev.get_available_connections()
    mainloop = nmclient.mainloop()
    if not connections:
        # No callback is expected, so we should call the next one.
        mainloop.execute_next_action()
        return

    user_data = mainloop
    for con in connections:
        con.delete_async(
            mainloop.cancellable,
            _delete_connection_callback,
            user_data,
        )


def _delete_connection_callback(src_object, result, user_data):
    mainloop = user_data
    try:
        success = src_object.delete_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection deletion aborted: error=%s', e)
        else:
            mainloop.quit('Connection deletion failed: error={}'.format(e))
        return

    devname = src_object.get_interface_name()
    if success:
        logging.debug('Connection deletion succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Connection deletion failed: '
            'dev={}, error=unknown'.format(devname))


def get_device_by_name(devname):
    client = nmclient.client()
    return client.get_device_by_iface(devname)


def list_devices():
    client = nmclient.client(refresh=True)
    return client.get_devices()


def get_device_common_info(dev):
    return {
        'name': dev.get_iface(),
        'type_id': dev.get_device_type(),
        'type_name': dev.get_type_description(),
        'state': dev.get_state(),
    }
