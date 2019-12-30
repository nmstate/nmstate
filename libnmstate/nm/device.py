#
# Copyright (c) 2018-2019 Red Hat, Inc.
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


def activate(ctx, dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    conn = connection.ConnectionProfile(ctx)
    conn.nmdevice = dev
    conn.con_id = connection_id
    conn.activate()


def deactivate(ctx, dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    act_con = ac.ActiveConnection(ctx)
    act_con.nmdevice = dev
    act_con.deactivate()


def delete(ctx, dev):
    connections = dev.get_available_connections()
    for con in connections:
        con_profile = connection.ConnectionProfile(ctx, con)
        con_profile.delete()


def reapply(ctx, dev, connection_profile):
    ctx.mainloop.push_action(_safe_reapply_async, ctx, dev, connection_profile)


def _safe_reapply_async(ctx, dev, connection_profile):
    cancellable = ctx.mainloop.new_cancellable()

    version_id = 0
    flags = 0
    user_data = ctx, dev, cancellable
    dev.reapply_async(
        connection_profile,
        version_id,
        flags,
        cancellable,
        _reapply_callback,
        user_data,
    )


def _reapply_callback(src_object, result, user_data):
    ctx, nmdev, cancellable = user_data
    ctx.mainloop.drop_cancellable(cancellable)

    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        if ctx.mainloop.is_action_canceled(e):
            logging.debug("Device reapply aborted on %s: error=%s", devname, e)
        else:
            ctx.mainloop.quit(
                "Device reapply failed on {}: error={}".format(devname, e)
            )
        return

    if success:
        logging.debug("Device reapply succeeded: dev=%s", devname)
        ctx.mainloop.execute_next_action()
    else:
        ctx.mainloop.quit(
            "Device reapply failed: dev={}, error=unknown".format(devname)
        )


def modify(ctx, dev, connection_profile):
    """
    Modify the given connection profile on the device.
    Implemented by the reapply operation with a fallback to the
    connection profile activation.
    """
    ctx.mainloop.push_action(_safe_modify_async, ctx, dev, connection_profile)


def _safe_modify_async(ctx, dev, connection_profile):
    cancellable = ctx.mainloop.new_cancellable()

    version_id = 0
    flags = 0
    user_data = ctx, dev, cancellable
    dev.reapply_async(
        connection_profile,
        version_id,
        flags,
        cancellable,
        _modify_callback,
        user_data,
    )


def _modify_callback(src_object, result, user_data):
    ctx, nmdev, cancellable = user_data
    ctx.mainloop.drop_cancellable(cancellable)

    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        if ctx.mainloop.is_action_canceled(e):
            logging.debug("Device reapply aborted on %s: error=%s", devname, e)
        else:
            logging.debug(
                "Device reapply failed on %s: error=%s\n"
                "Fallback to device activation",
                devname,
                e,
            )
            _activate_async(ctx, src_object)
        return

    if success:
        logging.debug("Device reapply succeeded: dev=%s", devname)
        ctx.mainloop.execute_next_action()
    else:
        logging.debug(
            "Device reapply failed, fallback to device activation: dev=%s, "
            "error=unknown",
            devname,
        )
        _activate_async(ctx, src_object)


def _activate_async(ctx, dev):
    conn = connection.ConnectionProfile(ctx)
    conn.nmdevice = dev
    if dev:
        # Workaround of https://bugzilla.redhat.com/show_bug.cgi?id=1772470
        dev.set_managed(True)
    conn.safe_activate_async()


def delete_device(ctx, nmdev):
    ctx.mainloop.push_action(_safe_delete_device_async, ctx, nmdev)


def _safe_delete_device_async(ctx, nmdev):
    user_data = ctx, nmdev
    nmdev.delete_async(
        ctx.mainloop.cancellable, _delete_device_callback, user_data
    )


def _delete_device_callback(src_object, result, user_data):
    ctx, nmdev = user_data
    try:
        success = src_object.delete_finish(result)
    # pylint: disable=catching-non-exception
    except nmclient.GLib.GError as e:
        # pylint: enable=catching-non-exception
        if e.matches(
            nmclient.Gio.DBusError.quark(),
            nmclient.Gio.DBusError.UNKNOWN_METHOD,
        ) or (
            e.matches(
                nmclient.NM.DeviceError.quark(),
                nmclient.NM.DeviceError.NOTSOFTWARE,
            )
            and nmdev.is_software()
        ):
            logging.debug(
                "Device %s has been already deleted: error=%s",
                nmdev.get_iface(),
                e,
            )
            ctx.mainloop.execute_next_action()
        else:
            ctx.mainloop.quit(
                "Device deletion failed on {}: error={}".format(
                    nmdev.get_iface(), e
                )
            )
        return
    except Exception as e:
        if ctx.mainloop.is_action_canceled(e):
            logging.debug(
                "Device deletion aborted on %s: error=%s", nmdev.get_iface(), e
            )
        else:
            ctx.mainloop.quit(
                "Device deletion failed on {}: error={}".format(
                    nmdev.get_iface(), e
                )
            )
        return

    devname = src_object.get_iface()
    if success:
        logging.debug("Device deletion succeeded: dev=%s", devname)
        ctx.mainloop.execute_next_action()
    else:
        ctx.mainloop.quit(
            "Device deletion failed: dev={}, error=unknown".format(devname)
        )


def get_device_by_name(ctx, devname):
    return ctx.client.get_device_by_iface(devname)


def list_devices(ctx):
    return ctx.client.get_devices()


def get_device_common_info(dev):
    return {
        "name": dev.get_iface(),
        "type_id": dev.get_device_type(),
        "type_name": dev.get_type_description(),
        "state": dev.get_state(),
    }
