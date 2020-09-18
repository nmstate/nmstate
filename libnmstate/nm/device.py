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
from . import profile_state
from .common import NM
from .common import GLib


NM_DBUS_INTERFACE_DEVICE = f"{NM.DBUS_INTERFACE}.Device"
NM_USE_DEFAULT_TIMEOUT_VALUE = -1


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


def modify(context, nm_profile):
    """
    Modify the given connection profile on the device.
    Implemented by the reapply operation with a fallback to the
    connection profile activation.
    """
    nm_ac = nm_profile.nmdev.get_active_connection()
    if profile_state.is_activated(nm_ac, nm_profile.nmdev):
        version_id = 0
        flags = 0
        action = f"Reapply device config: {nm_profile.nmdev.get_iface()}"
        context.register_async(action)
        user_data = context, nm_profile, action
        nm_profile.nmdev.reapply_async(
            nm_profile.profile,
            version_id,
            flags,
            context.cancellable,
            _modify_callback,
            user_data,
        )
    else:
        _activate_async(context, nm_profile)


def _modify_callback(src_object, result, user_data):
    context, nm_profile, action = user_data
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
        _activate_async(context, nm_profile)
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
        _activate_async(context, nm_profile)


def _activate_async(context, nm_profile):
    if nm_profile.nmdev:
        # Workaround of https://bugzilla.redhat.com/show_bug.cgi?id=1772470
        mark_device_as_managed(context, nm_profile.nmdev)
    nm_profile.activate()


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


def is_externally_managed(nmdev):
    nm_ac = nmdev.get_active_connection()
    return nm_ac and NM.ActivationStateFlags.EXTERNAL & nm_ac.get_state_flags()


def mark_device_as_managed(context, nm_dev):
    action = f"Set device as managed: {nm_dev.get_iface()}"
    context.register_async(action, fast=True)
    user_data = context, action
    context.client.dbus_set_property(
        NM.Object.get_path(nm_dev),
        NM_DBUS_INTERFACE_DEVICE,
        "Managed",
        GLib.Variant.new_boolean(True),
        NM_USE_DEFAULT_TIMEOUT_VALUE,
        context.cancellable,
        _set_managed_callback,
        user_data,
    )
    context.wait_all_finish()


def _set_managed_callback(_src_object, _result, user_data):
    context, action = user_data
    # There is no document mention this action might fail
    # If anything goes wrong, we trust verifcation stage can detect it.
    context.finish_async(action)
