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

from . import active_connection as ac
from . import connection
from . import nmclient


def activate(dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    conn = connection.ConnectionProfile()
    conn.nmdevice = dev
    conn.con_id = connection_id
    conn.activate()


def deactivate(dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    act_con = ac.ActiveConnection()
    act_con.nmdevice = dev
    act_con.deactivate()


def delete(dev):
    connections = dev.get_available_connections()
    for con in connections:
        con_profile = connection.ConnectionProfile(con)
        con_profile.delete()


def reapply(dev, connection_profile):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_reapply_async, dev, connection_profile)


def _safe_reapply_async(dev, connection_profile):
    mainloop = nmclient.mainloop()
    cancellable = mainloop.new_cancellable()

    version_id = 0
    flags = 0
    user_data = mainloop, dev, cancellable
    dev.reapply_async(
        connection_profile,
        version_id,
        flags,
        cancellable,
        _reapply_callback,
        user_data,
    )


def _reapply_callback(src_object, result, user_data):
    mainloop, nmdev, cancellable = user_data
    mainloop.drop_cancellable(cancellable)

    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug("Device reapply aborted on %s: error=%s", devname, e)
        else:
            mainloop.quit(
                "Device reapply failed on {}: error={}".format(devname, e)
            )
        return

    if success:
        logging.debug("Device reapply succeeded: dev=%s", devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            "Device reapply failed: dev={}, error=unknown".format(devname)
        )


def modify(dev, connection_profile):
    """
    Modify the given connection profile on the device.
    Implemented by the reapply operation with a fallback to the
    connection profile activation.
    """
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_modify_async, dev, connection_profile)


def _safe_modify_async(dev, connection_profile):
    mainloop = nmclient.mainloop()
    cancellable = mainloop.new_cancellable()

    version_id = 0
    flags = 0
    user_data = mainloop, dev, cancellable
    dev.reapply_async(
        connection_profile,
        version_id,
        flags,
        cancellable,
        _modify_callback,
        user_data,
    )


def _modify_callback(src_object, result, user_data):
    mainloop, nmdev, cancellable = user_data
    mainloop.drop_cancellable(cancellable)

    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug("Device reapply aborted on %s: error=%s", devname, e)
        else:
            logging.debug(
                "Device reapply failed on %s: error=%s\n"
                "Fallback to device activation",
                devname,
                e,
            )
            _activate_async(src_object)
        return

    if success:
        logging.debug("Device reapply succeeded: dev=%s", devname)
        mainloop.execute_next_action()
    else:
        logging.debug(
            "Device reapply failed, fallback to device activation: dev=%s, "
            "error=unknown",
            devname,
        )
        _activate_async(src_object)


def _activate_async(dev):
    conn = connection.ConnectionProfile()
    conn.nmdevice = dev
    if dev:
        # Workaround of https://bugzilla.redhat.com/show_bug.cgi?id=1772470
        dev.set_managed(True)
    conn.safe_activate_async()


def delete_device(nmdev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_device_async, nmdev)


def _safe_delete_device_async(nmdev):
    mainloop = nmclient.mainloop()
    user_data = mainloop, nmdev, nmdev.get_iface()
    nmdev.delete_async(
        mainloop.cancellable, _delete_device_callback, user_data
    )


def _delete_device_callback(src_object, result, user_data):
    mainloop, nmdev, iface = user_data
    error = None
    try:
        src_object.delete_finish(result)
    except Exception as e:
        error = e
        if mainloop.is_action_canceled(error):
            logging.debug(
                "Device deletion aborted on %s: error=%s", iface, error
            )
            return

    if not nmdev.is_real():
        logging.debug("Interface is not real anymore: iface=%s", iface)
        if error:
            logging.debug(
                "Ignored error: %s", error,
            )

        mainloop.execute_next_action()
    else:
        mainloop.quit(
            f"Device deletion failed on {iface} ({nmdev.get_path()}): "
            f"error={error or 'unknown'}"
        )


def get_device_by_name(devname):
    client = nmclient.client()
    return client.get_device_by_iface(devname)


def list_devices():
    client = nmclient.client()
    return client.get_devices()


def get_device_common_info(dev):
    return {
        "name": dev.get_iface(),
        "type_id": dev.get_device_type(),
        "type_name": dev.get_type_description(),
        "state": dev.get_state(),
    }
