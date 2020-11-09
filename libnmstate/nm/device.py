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
from libnmstate.schema import InterfaceType

from .common import NM
from .common import GLib
from .macvlan import is_macvtap
from .translator import Nm2Api


NM_DBUS_INTERFACE_DEVICE = f"{NM.DBUS_INTERFACE}.Device"
NM_USE_DEFAULT_TIMEOUT_VALUE = -1


class DeviceReapply:
    def __init__(
        self,
        ctx,
        iface_name,
        iface_type,
        nm_dev,
        nm_simple_conn,
        profile_activation,
    ):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_dev = nm_dev
        self._nm_simple_conn = nm_simple_conn
        self._profile_activation = profile_activation

    def run(self):
        """
        Modify the given connection profile on the device without bring the
        interface down.
        If failed, fall back to normal profile activation
        """
        version_id = 0
        flags = 0
        action = (
            f"Reapply device config: {self._iface_name} {self._iface_type} "
            f"{self._nm_simple_conn.get_uuid()}"
        )
        self._ctx.register_async(action)
        user_data = action
        self._nm_dev.reapply_async(
            self._nm_simple_conn,
            version_id,
            flags,
            self._ctx.cancellable,
            self._reapply_callback,
            user_data,
        )

    def _reapply_callback(self, nm_dev, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        try:
            success = nm_dev.reapply_finish(result)
        except Exception as e:
            logging.debug(
                f"Device reapply failed on {self._iface_name} "
                f"{self._iface_type}: error={e}, "
                "Fallback to device activation"
            )
            self._ctx.finish_async(action, suppress_log=True)
            self._profile_activation.run()
            return

        if success:
            self._ctx.finish_async(action)
        else:
            logging.debug(
                "Device reapply failed, fallback to device activation: "
                f"iface={self._iface_name}, type={self._iface_type} "
                "error='None returned from reapply_finish()'"
            )
            self._ctx.finish_async(action, suppress_log=True)
            self._profile_activation.run()


class DeviceDelete:
    def __init__(self, ctx, iface_name, iface_type, nm_dev):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_dev = nm_dev

    def run(self):
        action = f"Delete device: {self._iface_type} {self._iface_name}"
        user_data = action
        self._ctx.register_async(action)
        self._nm_dev.delete_async(
            self._ctx.cancellable, self._delete_device_callback, user_data
        )

    def _delete_device_callback(self, nm_dev, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        error = None
        try:
            nm_dev.delete_finish(result)
        except Exception as e:
            error = e

        if not nm_dev.is_real():
            logging.debug(
                f"Interface is deleted and not real/exist anymore: "
                f"iface={self._iface_name} type={self._iface_type}"
            )
            if error:
                logging.debug(f"Ignored error: {error}")
            self._ctx.finish_async(action)
        else:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: error={error or 'unknown'}"
                )
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


def is_externally_managed(nm_dev):
    nm_ac = nm_dev.get_active_connection()
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


def get_iface_type(nm_dev):
    # TODO: Below code are mimic from translator, need redesign on this
    iface_type = nm_dev.get_type_description()
    if iface_type != InterfaceType.ETHERNET:
        iface_type = Nm2Api.get_iface_type(nm_dev.get_type_description())
    if iface_type == InterfaceType.MAC_VLAN:
        # Check whether we are MAC VTAP as NM is treating both of them as
        # MAC VLAN.
        # BUG: We should use applied config here.
        nm_ac = nm_dev.get_active_connection()
        if nm_ac:
            nm_profile = nm_ac.get_connection()
            if nm_profile and is_macvtap(nm_profile):
                iface_type = InterfaceType.MAC_VTAP
    return iface_type


def get_nm_dev(ctx, iface_name, iface_type):
    """
    Return the first NM.Device matching iface_name and iface_type.
    We don't use `NM.Client.get_device_by_iface()` as nm_dev does not
    kernel interface, it could be OVS bridge or OVS port where name
    can duplicate with kernel interface name.
    """
    for nm_dev in ctx.client.get_devices():
        cur_iface_type = get_iface_type(nm_dev)
        if nm_dev.get_iface() == iface_name and (
            iface_type is None or cur_iface_type == iface_type
        ):
            return nm_dev
    return None
