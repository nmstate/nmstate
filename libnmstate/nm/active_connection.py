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

from .common import GLib
from .common import GObject
from .common import NM


NM_AC_STATE_CHANGED_SIGNAL = "state-changed"


class ActivationError(Exception):
    pass


class ActiveConnection:
    def __init__(self, context=None, nm_ac_con=None):
        self._ctx = context
        self._act_con = nm_ac_con

        nmdevs = None
        if nm_ac_con:
            nmdevs = nm_ac_con.get_devices()
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
        if (
            not act_connection
            or act_connection.props.state
            == NM.ActiveConnectionState.DEACTIVATED
        ):
            return

        if self._act_con != act_connection:
            raise NmstateLibnmError(
                "When deactivating active connection, the newly get "
                f"NM.ActiveConnection {act_connection}"
                f"is different from original request: {self._act_con}"
            )

        action = f"Deactivate profile: {self.devname}"
        self._ctx.register_async(action)
        handler_id = act_connection.connect(
            NM_AC_STATE_CHANGED_SIGNAL,
            self._wait_state_changed_callback,
            action,
        )
        if act_connection.props.state != NM.ActiveConnectionState.DEACTIVATING:
            user_data = (handler_id, action)
            self._ctx.client.deactivate_connection_async(
                act_connection,
                self._ctx.cancellable,
                self._deactivate_connection_callback,
                user_data,
            )

    def _wait_state_changed_callback(self, act_con, state, reason, action):
        if self._ctx.is_cancelled():
            return
        if act_con.props.state == NM.ActiveConnectionState.DEACTIVATED:
            logging.debug(
                "Connection deactivation succeeded on %s", self.devname,
            )
            self._ctx.finish_async(action)

    def _deactivate_connection_callback(self, src_object, result, user_data):
        handler_id, action = user_data
        if self._ctx.is_cancelled():
            if self._act_con:
                self._act_con.handler_disconnect(handler_id)
            return

        try:
            success = src_object.deactivate_connection_finish(result)
        except GLib.Error as e:
            if e.matches(
                NM.ManagerError.quark(), NM.ManagerError.CONNECTIONNOTACTIVE
            ):
                success = True
                logging.debug(
                    "Connection is not active on {}, no need to "
                    "deactivate".format(self.devname)
                )
            else:
                if self._act_con:
                    self._act_con.handler_disconnect(handler_id)
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: error={e}")
                )
                return
        except Exception as e:
            if self._act_con:
                self._act_con.handler_disconnect(handler_id)
            self._ctx.fail(
                NmstateLibnmError(
                    f"BUG: Unexpected error when activating {self.devname} "
                    f"error={e}"
                )
            )
            return

        if not success:
            if self._act_con:
                self._act_con.handler_disconnect(handler_id)
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: error='None returned from "
                    "deactivate_connection_finish()'"
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
        is_master_type = (
            GObject.type_is_a(nmdev, NM.DeviceBond)
            or GObject.type_is_a(nmdev, NM.DeviceBridge)
            or GObject.type_is_a(nmdev, NM.DeviceTeam)
            or GObject.type_is_a(nmdev, NM.DeviceOvsBridge)
        )
        return is_master_type
    return False
