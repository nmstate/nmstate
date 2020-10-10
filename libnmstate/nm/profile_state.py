#
# Copyright (c) 2020 Red Hat, Inc.
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

from .common import NM
from . import connection
from . import ipv4
from . import ipv6


class NmProfileState:
    def __init__(self, context):
        self._ctx = context
        self._ac_handlers = set()
        self._dev_handlers = set()

    def activate_connection_callback(self, src_object, result, user_data):
        action, profile = user_data
        nm_act_con = None
        if self._ctx.is_cancelled():
            self._activation_clean_up(profile)
            return
        try:
            nm_act_con = src_object.activate_connection_finish(result)
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))

        if nm_act_con is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: "
                    "error='None return from activate_connection_finish()'"
                )
            )
        else:
            logging.debug(
                "Connection activation initiated: dev=%s, con-state=%s",
                profile.devname,
                nm_act_con.props.state,
            )
            profile.nm_ac = nm_act_con
            profile.nmdev = self._ctx.get_nm_dev(profile.devname)

            if is_activated(profile.nm_ac, profile.nmdev):
                logging.debug(
                    "Connection activation succeeded: dev=%s, con-state=%s, "
                    "dev-state=%s, state-flags=%s",
                    profile.devname,
                    profile.nm_ac.get_state(),
                    profile.nmdev.get_state(),
                    profile.nm_ac.get_state_flags(),
                )
                self._activation_clean_up(profile)
                self._ctx.finish_async(action)
            elif self._is_activating(profile.nm_ac, profile.nmdev):
                self._wait_ac_activation(action, profile)
                if profile.nmdev:
                    self.wait_dev_activation(action, profile)
            else:
                if profile.nmdev:
                    error_msg = (
                        f"Connection {profile.simple_conn.get_uuid()} failed: "
                        f"state={profile.nm_ac.get_state()} "
                        f"reason={profile.nm_ac.get_state_reason()} "
                        f"dev_state={profile.nmdev.get_state()} "
                        f"dev_reason={profile.nmdev.get_state_reason()}"
                    )
                else:
                    error_msg = (
                        f"Connection {profile.simple_conn.get_id()} failed: "
                        f"state={profile.nm_ac.get_state()} "
                        f"reason={profile.nm_ac.get_state_reason()} dev=None"
                    )
                logging.error(error_msg)
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: {error_msg}")
                )

    def _wait_ac_activation(self, action, profile):
        user_data = action, profile
        self._ac_handlers.add(
            profile.nm_ac.connect(
                "state-changed", self._ac_state_change_callback, user_data,
            )
        )
        self._ac_handlers.add(
            profile.nm_ac.connect(
                "notify::state-flags",
                self._ac_state_flags_change_callback,
                user_data,
            )
        )

    def _ac_state_change_callback(
        self, _nm_act_con, _state, _reason, user_data
    ):
        action, profile = user_data
        if self._ctx.is_cancelled():
            self._activation_clean_up(profile)
            return
        self._activation_progress_check(action, profile)

    def _ac_state_flags_change_callback(self, _nm_act_con, _state, user_data):
        action, profile = user_data
        if self._ctx.is_cancelled():
            self._activation_clean_up(profile)
            return
        self._activation_progress_check(action, profile)

    def delete_profile_callback(self, src_object, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        try:
            success = src_object.delete_finish(result)
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))
            return

        if success:
            self._ctx.finish_async(action)
        else:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: error='None returned from "
                    "delete_finish'"
                )
            )

    def update2_callback(self, src_object, result, user_data):
        action = user_data
        if self._ctx.is_cancelled():
            return
        try:
            ret = src_object.update2_finish(result)
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error={e}")
            )
            return

        if ret is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error='None returned from "
                    "update2_finish()'"
                )
            )
        else:
            self._ctx.finish_async(action)

    def add_connection2_callback(self, src_object, result, user_data):
        action, profile = user_data
        if self._ctx.is_cancelled():
            return
        try:
            profile.remote_conn = src_object.add_connection2_finish(result)[0]
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error: {e}")
            )
            return

        if profile.remote_conn is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error: 'None returned from "
                    "add_connection2_finish()'"
                )
            )
        else:
            self._ctx.finish_async(action)

    def wait_dev_activation(self, action, profile):
        data = action, profile
        self._dev_handlers.add(
            profile.nmdev.connect(
                "state-changed", self._dev_state_change_callback, data
            )
        )

    def _dev_state_change_callback(
        self, _dev, _new_state, _old_state, _reason, _data
    ):
        action, profile = _data
        if self._ctx.is_cancelled():
            self._activation_clean_up(profile)
            return
        self._activation_progress_check(action, profile)

    def _activation_progress_check(self, action, profile):
        if self._ctx.is_cancelled():
            self._activation_clean_up(profile)
            return
        cur_nm_dev = self._ctx.get_nm_dev(profile.devname)
        if cur_nm_dev and cur_nm_dev != profile.nmdev:
            logging.debug(
                f"The NM.Device of profile {profile.devname} changed"
            )
            self._remove_dev_handlers(profile)
            profile.nmdev = cur_nm_dev
            self.wait_dev_activation(action, profile)

        cur_nm_ac = connection.get_device_active_connection(profile.nmdev)
        if cur_nm_ac and cur_nm_ac != profile.nm_ac:
            logging.debug(
                "Active connection of device {} has been replaced".format(
                    profile.devname
                )
            )
            self._remove_ac_handlers(profile)
            profile.nm_ac = cur_nm_ac
            self._wait_ac_activation(action, profile)
        if is_activated(profile.nm_ac, profile.nmdev):
            logging.debug(
                "Connection activation succeeded: dev=%s, con-state=%s, "
                "dev-state=%s, state-flags=%s",
                profile.devname,
                profile.nm_ac.get_state(),
                profile.nmdev.get_state(),
                profile.nm_ac.get_state_flags(),
            )
            self._activation_clean_up(profile)
            self._ctx.finish_async(action)
        elif not self._is_activating(profile.nm_ac, profile.nmdev):
            reason = f"{profile.nm_ac.get_state_reason()}"
            if profile.nmdev:
                reason += f" {profile.nmdev.get_state_reason()}"
            self._activation_clean_up(profile)
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed: reason={reason}")
            )

    def _activation_clean_up(self, profile):
        self._remove_ac_handlers(profile)
        self._remove_dev_handlers(profile)

    def _remove_ac_handlers(self, profile):
        for handler_id in self._ac_handlers:
            profile.nm_ac.handler_disconnect(handler_id)
        self._ac_handlers = set()

    def _remove_dev_handlers(self, profile):
        for handler_id in self._dev_handlers:
            profile.nmdev.handler_disconnect(handler_id)
        self._dev_handlers = set()

    def _is_activating(self, nm_ac, nm_dev):
        if not nm_ac or not nm_dev:
            return True
        if nm_dev.get_state_reason() == NM.DeviceStateReason.NEW_ACTIVATION:
            return True

        return (
            nm_ac.get_state() == NM.ActiveConnectionState.ACTIVATING
        ) and not is_activated(nm_ac, nm_dev)


def get_applied_config_callback(nm_dev, result, user_data):
    iface_name, action, applied_configs, context = user_data
    context.finish_async(action)
    try:
        remote_conn, _ = nm_dev.get_applied_connection_finish(result)
        # TODO: We should use both interface name and type as key below.
        applied_configs[nm_dev.get_iface()] = remote_conn
    except Exception as e:
        logging.warning(
            "Failed to retrieve applied config for device "
            f"{iface_name}: {e}"
        )


def is_activated(nm_ac, nm_dev):
    if not (nm_ac and nm_dev):
        return False

    state = nm_ac.get_state()
    if state == NM.ActiveConnectionState.ACTIVATED:
        return True
    elif state == NM.ActiveConnectionState.ACTIVATING:
        ac_state_flags = nm_ac.get_state_flags()
        nm_flags = NM.ActivationStateFlags
        ip4_is_dynamic = ipv4.is_dynamic(nm_ac)
        ip6_is_dynamic = ipv6.is_dynamic(nm_ac)
        if (
            ac_state_flags & nm_flags.IS_MASTER
            or (ip4_is_dynamic and ac_state_flags & nm_flags.IP6_READY)
            or (ip6_is_dynamic and ac_state_flags & nm_flags.IP4_READY)
            or (ip4_is_dynamic and ip6_is_dynamic)
        ):
            # For interface meet any condition below will be
            # treated as activated when reach IP_CONFIG state:
            #   * Is controller device.
            #   * DHCPv4 enabled with IP6_READY flag.
            #   * DHCPv6/Autoconf with IP4_READY flag.
            #   * DHCPv4 enabled with DHCPv6/Autoconf enabled.
            return (
                NM.DeviceState.IP_CONFIG
                <= nm_dev.get_state()
                <= NM.DeviceState.ACTIVATED
            )

    return False
