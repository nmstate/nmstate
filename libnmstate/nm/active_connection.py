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
from libnmstate.error import NmstateInternalError

from .common import GLib
from .common import NM
from .device import get_nm_dev
from .device import get_iface_type
from .device import mark_device_as_managed
from .ipv4 import is_dynamic as is_ipv4_dynamic
from .ipv6 import is_dynamic as is_ipv6_dynamic


NM_AC_STATE_CHANGED_SIGNAL = "state-changed"


def is_activated(nm_ac, nm_dev):
    if not (nm_ac and nm_dev):
        return False

    state = nm_ac.get_state()
    if state == NM.ActiveConnectionState.ACTIVATED:
        return True
    elif state == NM.ActiveConnectionState.ACTIVATING:
        ac_state_flags = nm_ac.get_state_flags()
        nm_flags = NM.ActivationStateFlags
        ip4_is_dynamic = is_ipv4_dynamic(nm_ac)
        ip6_is_dynamic = is_ipv6_dynamic(nm_ac)
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


def is_activating(nm_ac, nm_dev):
    if not nm_ac or not nm_dev:
        return True
    if nm_dev.get_state_reason() == NM.DeviceStateReason.NEW_ACTIVATION:
        return True

    return (
        nm_ac.get_state() == NM.ActiveConnectionState.ACTIVATING
    ) and not is_activated(nm_ac, nm_dev)


class ProfileActivation:
    def __init__(self, ctx, iface_name, iface_type, nm_profile, nm_dev):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_ac = None
        self._nm_dev = nm_dev
        self._nm_profile = nm_profile
        self._ac_handlers = set()
        self._dev_handlers = set()
        self._action = None

    def run(self):
        specific_object = None
        self._action = (
            f"Activate profile uuid:{self._nm_profile.get_uuid()} "
            f"iface:{self._iface_name} type: {self._iface_type}"
        )
        if self._nm_dev:
            # Workaround of https://bugzilla.redhat.com/1880420
            mark_device_as_managed(self._ctx, self._nm_dev)

        user_data = None
        self._ctx.register_async(self._action)
        self._ctx.client.activate_connection_async(
            self._nm_profile,
            self._nm_dev,
            specific_object,
            self._ctx.cancellable,
            self._activate_profile_callback,
            user_data,
        )

    @staticmethod
    def wait(ctx, nm_ac, nm_dev):
        activation = ProfileActivation(
            ctx,
            nm_dev.get_iface(),
            get_iface_type(nm_dev),
            None,
            nm_dev,
        )
        activation._nm_ac = nm_ac
        activation._action = (
            f"Waiting activation of {activation._iface_name} "
            f"{activation._iface_type}"
        )
        ctx.register_async(activation._action)
        activation._wait_profile_activation()

    def _activate_profile_callback(self, nm_client, result, _user_data):
        nm_ac = None
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        try:
            nm_ac = nm_client.activate_connection_finish(result)
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{self._action} failed: error={e}")
            )

        if nm_ac is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{self._action} failed: "
                    "error='None return from activate_connection_finish()'"
                )
            )
        else:
            logging.debug(
                f"Connection activation initiated: iface={self._iface_name} "
                f"type={self._iface_type} con-state={nm_ac.get_state()}"
            )
            self._nm_ac = nm_ac
            self._nm_dev = get_nm_dev(
                self._ctx, self._iface_name, self._iface_type
            )
            self._wait_profile_activation()

    def _wait_profile_activation(self):
        if is_activated(self._nm_ac, self._nm_dev):
            logging.debug(
                "Connection activation succeeded: "
                f"iface={self._iface_name}, type={self._iface_type}, "
                f"con_state={self._nm_ac.get_state()}, "
                f"dev_state={self._nm_dev.get_state()}, "
                f"state_flags={self._nm_ac.get_state_flags()}"
            )
            self._activation_clean_up()
            self._ctx.finish_async(self._action)
        elif is_activating(self._nm_ac, self._nm_dev):
            if self._nm_ac:
                self._wait_nm_ac_activation()
            if self._nm_dev:
                self._wait_nm_dev_activation()
            if not self._nm_ac and not self._nm_dev:
                self._ctx.fail(
                    NmstateInternalError(
                        f"{self._action} failed: no nm_ac or nm_dev"
                    )
                )
        else:
            if self._nm_dev:
                error_msg = (
                    f"Connection {self._nm_profile.get_uuid()} failed: "
                    f"state={self._nm_ac.get_state()} "
                    f"reason={self._nm_ac.get_state_reason()} "
                    f"dev_state={self._nm_dev.get_state()} "
                    f"dev_reason={self._nm_dev.get_state_reason()}"
                )
            else:
                error_msg = (
                    f"Connection {self._nm_profile.get_uuid()} failed: "
                    f"state={self._nm_ac.get_state()} "
                    f"reason={self._nm_ac.get_state_reason()} dev=None"
                )
            self._activation_clean_up()
            logging.error(error_msg)
            self._ctx.fail(
                NmstateLibnmError(f"{self._action} failed: {error_msg}")
            )

    def _activation_clean_up(self):
        self._remove_ac_handlers()
        self._remove_dev_handlers()

    def _remove_ac_handlers(self):
        for handler_id in self._ac_handlers:
            self._nm_ac.handler_disconnect(handler_id)
        self._ac_handlers = set()

    def _remove_dev_handlers(self):
        for handler_id in self._dev_handlers:
            self._nm_dev.handler_disconnect(handler_id)
        self._dev_handlers = set()

    def _wait_nm_ac_activation(self):
        user_data = None
        self._ac_handlers.add(
            self._nm_ac.connect(
                NM_AC_STATE_CHANGED_SIGNAL,
                self._ac_state_change_callback,
                user_data,
            )
        )
        self._ac_handlers.add(
            self._nm_ac.connect(
                "notify::state-flags",
                self._ac_state_flags_change_callback,
                user_data,
            )
        )

    def _ac_state_change_callback(self, _nm_ac, _state, _reason, _user_data):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check()

    def _ac_state_flags_change_callback(self, _nm_ac, _state, _user_data):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check()

    def _wait_nm_dev_activation(self):
        user_data = None
        self._dev_handlers.add(
            self._nm_dev.connect(
                "state-changed", self._dev_state_change_callback, user_data
            )
        )

    def _dev_state_change_callback(
        self, _nm_dev, _new_state, _old_state, _reason, _user_data
    ):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check()

    def _activation_progress_check(self):
        cur_nm_dev = get_nm_dev(self._ctx, self._iface_name, self._iface_type)
        if cur_nm_dev and cur_nm_dev != self._nm_dev:
            logging.debug(
                f"The NM.Device of profile {self._iface_name} "
                f"{self._iface_type} changed"
            )
            self._remove_dev_handlers()
            self._nm_dev = cur_nm_dev
            self._wait_nm_dev_activation()

        if cur_nm_dev:
            cur_nm_ac = cur_nm_dev.get_active_connection()
            if cur_nm_ac and cur_nm_ac != self._nm_ac:
                logging.debug(
                    f"Active connection of device {self._iface_name} "
                    "has been replaced"
                )
                self._remove_ac_handlers()
                self._nm_ac = cur_nm_ac
                self._wait_nm_ac_activation()

        if is_activated(self._nm_ac, self._nm_dev):
            logging.debug(
                "Connection activation succeeded: "
                f"iface={self._iface_name}, type={self._iface_type}, "
                f"con_state={self._nm_ac.get_state()}, "
                f"dev_state={self._nm_dev.get_state()}, "
                f"state_flags={self._nm_ac.get_state_flags()}"
            )
            self._activation_clean_up()
            self._ctx.finish_async(self._action)
        elif not is_activating(self._nm_ac, self._nm_dev):
            reason = f"{self._nm_ac.get_state_reason()}"
            if self._nm_dev:
                reason += f" {self._nm_dev.get_state_reason()}"
            self._activation_clean_up()
            self._ctx.fail(
                NmstateLibnmError(f"{self._action} failed: reason={reason}")
            )


class ActiveConnectionDeactivate:
    def __init__(self, ctx, iface_name, iface_type, nm_ac):
        self._ctx = ctx
        self._iface_name = iface_name
        self._iface_type = iface_type
        self._nm_ac = nm_ac

    def run(self):
        if self._nm_ac.props.state == NM.ActiveConnectionState.DEACTIVATED:
            return

        action = f"Deactivate profile: {self._iface_name} {self._iface_type}"
        self._ctx.register_async(action)
        handler_id = self._nm_ac.connect(
            NM_AC_STATE_CHANGED_SIGNAL,
            self._wait_state_changed_callback,
            action,
        )
        if self._nm_ac.props.state != NM.ActiveConnectionState.DEACTIVATING:
            user_data = (handler_id, action)
            self._ctx.client.deactivate_connection_async(
                self._nm_ac,
                self._ctx.cancellable,
                self._deactivate_connection_callback,
                user_data,
            )

    def _wait_state_changed_callback(self, nm_ac, state, reason, action):
        if self._ctx.is_cancelled():
            return
        if nm_ac.props.state == NM.ActiveConnectionState.DEACTIVATED:
            logging.debug(
                "Connection deactivation succeeded on %s",
                self._iface_name,
            )
            self._ctx.finish_async(action)

    def _deactivate_connection_callback(self, nm_client, result, user_data):
        handler_id, action = user_data
        if self._ctx.is_cancelled():
            if self._nm_ac:
                self._nm_ac.handler_disconnect(handler_id)
            return

        try:
            success = nm_client.deactivate_connection_finish(result)
        except GLib.Error as e:
            if e.matches(
                NM.ManagerError.quark(), NM.ManagerError.CONNECTIONNOTACTIVE
            ):
                success = True
                logging.debug(
                    "Connection is not active on {}, no need to "
                    "deactivate".format(self._iface_name)
                )
                if self._nm_ac:
                    self._nm_ac.handler_disconnect(handler_id)
                self._ctx.finish_async(action)
            else:
                if self._nm_ac:
                    self._nm_ac.handler_disconnect(handler_id)
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: error={e}")
                )
                return
        except Exception as e:
            if self._nm_ac:
                self._nm_ac.handler_disconnect(handler_id)
            self._ctx.fail(
                NmstateLibnmError(
                    "BUG: Unexpected error when activating "
                    f"{self._iface_name} error={e}"
                )
            )
            return

        if not success:
            if self._nm_ac:
                self._nm_ac.handler_disconnect(handler_id)
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: error='None returned from "
                    "deactivate_connection_finish()'"
                )
            )
