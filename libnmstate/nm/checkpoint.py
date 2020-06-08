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

from libnmstate.error import NmstateConflictError
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstatePermissionError
from libnmstate.nm import connection
from libnmstate.nm import common
from .connection import is_activated


def get_checkpoints(nm_client):
    checkpoints = [c.get_path() for c in nm_client.get_checkpoints()]
    return checkpoints


class CheckPoint:
    def __init__(self, nm_context, timeout=60, dbuspath=None):
        self._ctx = nm_context
        self._timeout = timeout
        self._dbuspath = dbuspath
        self._timeout_source = None

    def __str__(self):
        return self._dbuspath

    @staticmethod
    def create(nm_context, timeout=60):
        cp = CheckPoint(nm_context=nm_context, timeout=timeout)
        cp._create()
        return cp

    def _create(self):
        devs = []
        timeout = self._timeout
        cp_flags = (
            common.NM.CheckpointCreateFlags.DELETE_NEW_CONNECTIONS
            | common.NM.CheckpointCreateFlags.DISCONNECT_NEW_DEVICES
        )

        try:
            self._ctx.client.checkpoint_create(
                devs,
                timeout,
                cp_flags,
                self._ctx.cancellable,
                self._checkpoint_create_callback,
                None,
            )
        except Exception as e:
            raise NmstateLibnmError(
                "Failed to create checkpoint: " "{}".format(e)
            )
        self._ctx.register_async("Create checkpoint")
        self._ctx.wait_all_finish()
        self._add_checkpoint_refresh_timeout()

    def _add_checkpoint_refresh_timeout(self):
        self._timeout_source = common.GLib.timeout_source_new(
            self._timeout * 500
        )
        self._timeout_source.set_callback(
            self._refresh_checkpoint_timeout, None
        )
        self._timeout_source.attach(self._ctx.context)

    def clean_up(self):
        self._remove_checkpoint_refresh_timeout()

    def _remove_checkpoint_refresh_timeout(self):
        if self._timeout_source:
            self._timeout_source.destroy()
            self._timeout_source = None

    def _refresh_checkpoint_timeout(self, _user_data):
        cancellable, cb, cb_data = (None, None, None)

        if self._ctx and self._ctx.client:
            self._ctx.client.checkpoint_adjust_rollback_timeout(
                self._dbuspath, self._timeout, cancellable, cb, cb_data
            )
            return common.GLib.SOURCE_CONTINUE
        else:
            return common.GLib.SOURCE_REMOVE

    def destroy(self):
        if self._dbuspath:
            action = f"Destroy checkpoint {self._dbuspath}"
            userdata = action
            try:
                self._ctx.client.checkpoint_destroy(
                    self._dbuspath,
                    self._ctx.cancellable,
                    self._checkpoint_destroy_callback,
                    userdata,
                )
            except Exception as e:
                raise NmstateLibnmError(
                    "Failed to destroy checkpoint {}: "
                    "{}".format(self._dbuspath, e)
                )
            finally:
                self.clean_up()
            logging.debug(f"Checkpoint {self._dbuspath} destroyed")
            self._ctx.register_async(action)
            self._ctx.wait_all_finish()

    def rollback(self):
        if self._dbuspath:
            action = f"Rollback to checkpoint {self._dbuspath}"
            userdata = action
            try:
                self._ctx.client.checkpoint_rollback(
                    self._dbuspath,
                    self._ctx.cancellable,
                    self._checkpoint_rollback_callback,
                    userdata,
                )
            except Exception as e:
                raise NmstateLibnmError(
                    "Failed to rollback checkpoint {}: {}".format(
                        self._dbuspath, e
                    )
                )
            finally:
                self.clean_up()
            logging.debug(f"Checkpoint {self._dbuspath} rollback executed")
            self._ctx.register_async(action)
            self._ctx.wait_all_finish()

    def _checkpoint_create_callback(self, client, result, data):
        try:
            cp = client.checkpoint_create_finish(result)
            if cp:
                logging.debug(
                    "Checkpoint {} created for all devices".format(
                        self._dbuspath
                    )
                )
                self._dbuspath = cp.get_path()
                self._ctx.finish_async("Create checkpoint")
            else:
                error_msg = (
                    f"dbuspath={self._dbuspath} "
                    f"timeout={self._timeout} "
                    f"callback result={cp}"
                )
                self._ctx.fail(
                    NmstateLibnmError(f"Checkpoint create failed: {error_msg}")
                )
        except common.GLib.Error as e:
            if e.matches(
                common.NM.ManagerError.quark(),
                common.NM.ManagerError.PERMISSIONDENIED,
            ):
                self._ctx.fail(
                    NmstatePermissionError(
                        "Checkpoint create failed due to insufficient"
                        " permission"
                    )
                )
            elif e.matches(
                common.NM.ManagerError.quark(),
                common.NM.ManagerError.INVALIDARGUMENTS,
            ):
                self._ctx.fail(
                    NmstateConflictError(
                        "Checkpoint create failed due to a"
                        " conflict with an existing checkpoint"
                    )
                )
            else:
                self._ctx.fail(
                    NmstateLibnmError(f"Checkpoint create failed: error={e}")
                )
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"Checkpoint create failed: error={e}")
            )

    def _checkpoint_rollback_callback(self, client, result, data):
        action = data
        try:
            self._check_rollback_result(client, result, self._dbuspath)
            self._dbuspath = None
            self._ctx.finish_async(action)
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"Checkpoint rollback failed: error={e}")
            )

    def _check_rollback_result(self, client, result, dbus_path):
        ret = client.checkpoint_rollback_finish(result)
        logging.debug(f"Checkpoint {dbus_path} rollback executed")
        for path in ret:
            nm_dev = client.get_device_by_path(path)
            iface = path if nm_dev is None else nm_dev.get_iface()
            if (
                nm_dev.get_state_reason()
                == common.NM.DeviceStateReason.NEW_ACTIVATION
            ) or nm_dev.get_state() == common.NM.DeviceState.IP_CONFIG:
                nm_ac = nm_dev.get_active_connection()
                if not is_activated(nm_ac, nm_dev):
                    profile = connection.ConnectionProfile(self._ctx)
                    profile.nmdevice = nm_dev
                    action = f"Waiting for rolling back {iface}"
                    self._ctx.register_async(action)
                    profile.wait_dev_activation(action)
            if ret[path] != 0:
                logging.error(f"Interface {iface} rollback failed")
            else:
                logging.debug(f"Interface {iface} rollback succeeded")

    def _checkpoint_destroy_callback(self, client, result, data):
        action = data
        try:
            client.checkpoint_destroy_finish(result)
            logging.debug(f"Checkpoint {self._dbuspath} destroy executed")
            self._dbuspath = None
            self._ctx.finish_async(action)
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(
                    f"Checkpoint {self._dbuspath} destroy failed: "
                    f"error={e}"
                )
            )
