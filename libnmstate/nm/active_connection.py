#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from . import ipv4
from . import ipv6
from .common import GLib
from .common import GObject
from .common import NM


NM_MANAGER_ERROR_DOMAIN = "nm-manager-error-quark"


class ActivationError(Exception):
    pass


class ActiveConnection:
    def __init__(self, context=None, ac=None):
        self._ctx = context
        self._act_con = ac

        nmdevs = None
        if ac:
            nmdevs = ac.get_devices()
        self._nmdev = nmdevs[0] if nmdevs else None

    def import_by_device(self, nmdev=None):
        assert self._act_con is None

        if nmdev:
            self._nmdev = nmdev
        if self._nmdev:
            self._act_con = self._nmdev.get_active_connection()

    def deactivate(self):
        """
        Deactivating the current active connection,
        The profile itself is not removed.

        For software devices, deactivation removes the devices from the kernel.
        """
        act_connection = self._nmdev.get_active_connection()
        if not act_connection or act_connection.props.state in (
            NM.ActiveConnectionState.DEACTIVATING,
            NM.ActiveConnectionState.DEACTIVATED,
        ):
            # Nothing left to do here, call the next action.
            return

        action = f"Deactivate profile: {self.devname}"
        self._ctx.register_async(action)
        user_data = action
        self._ctx.client.deactivate_connection_async(
            act_connection,
            self._ctx.cancellable,
            self._deactivate_connection_callback,
            user_data,
        )

    def _deactivate_connection_callback(self, src_object, result, user_data):
        action = user_data
        try:
            success = src_object.deactivate_connection_finish(result)
        except Exception as e:
            if (
                isinstance(e, GLib.GError)
                # pylint: disable=no-member
                and e.domain == NM_MANAGER_ERROR_DOMAIN
                and e.code == NM.ManagerError.CONNECTIONNOTACTIVE
                # pylint: enable=no-member
            ):
                success = True
                logging.debug(
                    "Connection is not active on {}, no need to "
                    "deactivate".format(self.devname)
                )
            else:
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: error={e}")
                )
                return

        if success:
            self._ctx.finish_async(action)
        else:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: "
                    f"error='None returned from deactivate_connection_finish()'"
                )
            )

    @property
    def nm_active_connection(self):
        return self._act_con

    @property
    def devname(self):
        if self._nmdev:
            return self._nmdev.get_iface()
        else:
            return None

    @property
    def nmdevice(self):
        return self._nmdev

    @nmdevice.setter
    def nmdevice(self, nmdev):
        assert self._nmdev is None
        self._nmdev = nmdev


def _is_device_master_type(nmdev):
    if nmdev:
        gobject = GObject
        is_master_type = (
            gobject.type_is_a(nmdev, NM.DeviceBond)
            or gobject.type_is_a(nmdev, NM.DeviceBridge)
            or gobject.type_is_a(nmdev, NM.DeviceTeam)
            or gobject.type_is_a(nmdev, NM.DeviceOvsBridge)
        )
        return is_master_type
    return False
