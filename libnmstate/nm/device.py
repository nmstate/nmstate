#
# Copyright (c) 2018-2020 Red Hat, Inc.
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

import logging

from libnmstate.error import NmstateLibnmError

from . import active_connection as ac
from . import connection


def activate(context, dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    conn = connection.ConnectionProfile(context)
    conn.nmdevice = dev
    conn.con_id = connection_id
    conn.activate()


def deactivate(context, dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    act_con = ac.ActiveConnection(context)
    act_con.nmdevice = dev
    act_con.import_by_device()
    act_con.deactivate()


def delete(context, dev):
    connections = dev.get_available_connections()
    for con in connections:
        con_profile = connection.ConnectionProfile(context, con)
        con_profile.delete()


def modify(context, nm_dev, connection_profile):
    """
    Modify the given connection profile on the device.
    Implemented by the reapply operation with a fallback to the
    connection profile activation.
    """
    nm_ac = nm_dev.get_active_connection()
    if connection.is_activated(nm_ac, nm_dev):
        version_id = 0
        flags = 0
        action = f"Reapply device config: {nm_dev.get_iface()}"
        context.register_async(action)
        user_data = context, nm_dev, action
        nm_dev.reapply_async(
            connection_profile,
            version_id,
            flags,
            context.cancellable,
            _modify_callback,
            user_data,
        )
    else:
        _activate_async(context, nm_dev)


def _modify_callback(src_object, result, user_data):
    context, nmdev, action = user_data
    if context.is_cancelled():
        return
    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        logging.debug(
            "Device reapply failed on %s: error=%s\n"
            "Fallback to device activation",
            devname,
            e,
        )
        context.finish_async(action, suppress_log=True)
        _activate_async(context, src_object)
        return

    if success:
        context.finish_async(action)
    else:
        logging.debug(
            "Device reapply failed, fallback to device activation: dev=%s, "
            "error='None returned from reapply_finish()'",
            devname,
        )
        context.finish_async(action, suppress_log=True)
        _activate_async(context, src_object)


def _activate_async(context, dev):
    conn = connection.ConnectionProfile(context)
    conn.con_id = dev.get_iface()
    conn.nmdevice = dev
    if dev:
        # Workaround of https://bugzilla.redhat.com/show_bug.cgi?id=1772470
        dev.set_managed(True)
    conn.activate()


def delete_device(context, nmdev):
    iface_name = nmdev.get_iface()
    if iface_name:
        action = f"Delete device: {nmdev.get_iface()}"
        user_data = context, nmdev, action, nmdev.get_iface()
        context.register_async(action)
        nmdev.delete_async(
            context.cancellable, _delete_device_callback, user_data
        )


def _delete_device_callback(src_object, result, user_data):
    context, nmdev, action, iface_name = user_data
    if context.is_cancelled():
        return
    error = None
    try:
        src_object.delete_finish(result)
    except Exception as e:
        error = e

    if not nmdev.is_real():
        logging.debug("Interface is not real anymore: iface=%s", iface_name)
        if error:
            logging.debug("Ignored error: %s", error)
        context.finish_async(action)
    else:
        context.fail(
            NmstateLibnmError(f"{action} failed: error={error or 'unknown'}")
        )


def list_devices(client):
    return client.get_devices()


def get_device_common_info(dev):
    return {
        "name": dev.get_iface(),
        "type_id": dev.get_device_type(),
        "type_name": dev.get_type_description(),
        "state": dev.get_state(),
    }
