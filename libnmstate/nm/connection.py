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
import uuid

from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstateInternalError

from .common import NM
from . import ipv4
from . import ipv6

ACTIVATION_TIMEOUT_FOR_BRIDGE = 35  # Bridge STP requires 30 seconds.


class ConnectionProfile:
    def __init__(self, context, profile=None):
        self._ctx = context
        self._con_profile = profile
        self._nm_dev = None
        self._con_id = None
        self._nm_ac = None
        self._ac_handlers = set()
        self._dev_handlers = set()

    def create(self, settings):
        self.profile = NM.SimpleConnection.new()
        for setting in settings:
            self.profile.add_setting(setting)

    def import_by_device(self, nmdev=None):
        ac = get_device_active_connection(nmdev or self.nmdevice)
        if ac:
            if nmdev:
                self.nmdevice = nmdev
            self.profile = ac.props.connection

    def import_by_id(self, con_id=None):
        if con_id:
            self.con_id = con_id
        if self.con_id:
            self.profile = self._ctx.client.get_connection_by_id(self.con_id)

    def update(self, con_profile, save_to_disk=True):
        flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
        if save_to_disk:
            flags |= NM.SettingsUpdate2Flags.TO_DISK
        else:
            flags |= NM.SettingsUpdate2Flags.IN_MEMORY
        action = f"Update profile: {self.profile.get_id()}"
        user_data = action
        args = None

        self._ctx.register_async(action, fast=True)
        self.profile.update2(
            con_profile.profile.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            self._ctx.cancellable,
            self._update2_callback,
            user_data,
        )

    def add(self, save_to_disk=True):
        nm_add_conn2_flags = NM.SettingsAddConnection2Flags
        flags = nm_add_conn2_flags.BLOCK_AUTOCONNECT
        if save_to_disk:
            flags |= nm_add_conn2_flags.TO_DISK
        else:
            flags |= nm_add_conn2_flags.IN_MEMORY

        action = f"Add profile: {self.profile.get_id()}"
        self._ctx.register_async(action, fast=True)

        user_data = action
        args = None
        ignore_out_result = False  # Don't fall back to old AddConnection()
        self._ctx.client.add_connection2(
            self.profile.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            ignore_out_result,
            self._ctx.cancellable,
            self._add_connection2_callback,
            user_data,
        )

    def delete(self):
        if not self.profile:
            self.import_by_id()
            if not self.profile:
                self.import_by_device()
        if self.profile:
            action = (
                f"Delete profile: id:{self.profile.get_id()}, "
                f"uuid:{self.profile.get_uuid()}"
            )
            user_data = action
            self._ctx.register_async(action, fast=True)
            self.profile.delete_async(
                self._ctx.cancellable,
                self._delete_connection_callback,
                user_data,
            )

    def activate(self):
        if self.con_id:
            self.import_by_id()
        elif self.nmdevice:
            self.import_by_device()
        elif not self.profile:
            raise NmstateInternalError(
                "BUG: Failed  to find valid profile to activate: "
                f"id={self.con_id}, dev={self.devname}"
            )

        specific_object = None
        if self.profile:
            action = f"Activate profile: {self.profile.get_id()}"
        elif self.nmdevice:
            action = f"Activate profile: {self.nmdevice.get_iface()}"
        else:
            raise NmstateInternalError(
                "BUG: Cannot activate a profile with empty profile id and "
                "empty NM.Device"
            )
        user_data = action
        self._ctx.register_async(action)
        self._ctx.client.activate_connection_async(
            self.profile,
            self.nmdevice,
            specific_object,
            self._ctx.cancellable,
            self._active_connection_callback,
            user_data,
        )

    @property
    def profile(self):
        return self._con_profile

    @profile.setter
    def profile(self, con_profile):
        assert self._con_profile is None
        self._con_profile = con_profile

    @property
    def devname(self):
        if self._con_profile:
            return self._con_profile.get_interface_name()
        return None

    @property
    def nmdevice(self):
        return self._nm_dev

    @nmdevice.setter
    def nmdevice(self, dev):
        assert self._nm_dev is None
        self._nm_dev = dev

    @property
    def con_id(self):
        con_id = self._con_profile.get_id() if self._con_profile else None
        return self._con_id or con_id

    @con_id.setter
    def con_id(self, connection_id):
        assert self._con_id is None
        self._con_id = connection_id

    def get_setting_duplicate(self, setting_name):
        setting = None
        if self.profile:
            setting = self.profile.get_setting_by_name(setting_name)
            if setting:
                setting = setting.duplicate()
        return setting

    def _active_connection_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        action = user_data

        try:
            nm_act_con = src_object.activate_connection_finish(result)
        except Exception as e:
            self._ctx.fail(NmstateLibnmError(f"{action} failed: error={e}"))
            return

        if nm_act_con is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed: "
                    "error='None return from activate_connection_finish()'"
                )
            )
        else:
            devname = self.devname
            logging.debug(
                "Connection activation initiated: dev=%s, con-state=%s",
                devname,
                nm_act_con.props.state,
            )
            self._nm_ac = nm_act_con
            self._nm_dev = self._ctx.get_nm_dev(devname)

            if is_activated(self._nm_ac, self._nm_dev):
                self._ctx.finish_async(action)
            elif self._is_activating():
                self._wait_ac_activation(action)
                if self._nm_dev:
                    self.wait_dev_activation(action)
            else:
                if self._nm_dev:
                    error_msg = (
                        f"Connection {self.profile.get_id()} failed: "
                        f"state={self._nm_ac.get_state()} "
                        f"reason={self._nm_ac.get_state_reason()} "
                        f"dev_state={self._nm_dev.get_state()} "
                        f"dev_reason={self._nm_dev.get_state_reason()}"
                    )
                else:
                    error_msg = (
                        f"Connection {self.profile.get_id()} failed: "
                        f"state={self._nm_ac.get_state()} "
                        f"reason={self._nm_ac.get_state_reason()} dev=None"
                    )
                logging.error(error_msg)
                self._ctx.fail(
                    NmstateLibnmError(f"{action} failed: {error_msg}")
                )

    def _wait_ac_activation(self, action):
        self._ac_handlers.add(
            self._nm_ac.connect(
                "state-changed", self._ac_state_change_callback, action
            )
        )
        self._ac_handlers.add(
            self._nm_ac.connect(
                "notify::state-flags",
                self._ac_state_flags_change_callback,
                action,
            )
        )

    def wait_dev_activation(self, action):
        if self._nm_dev:
            self._dev_handlers.add(
                self._nm_dev.connect(
                    "state-changed", self._dev_state_change_callback, action
                )
            )

    def _dev_state_change_callback(
        self, _dev, _new_state, _old_state, _reason, action,
    ):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(action)

    def _ac_state_flags_change_callback(self, _nm_act_con, _state, action):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(action)

    def _ac_state_change_callback(self, _nm_act_con, _state, _reason, action):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        self._activation_progress_check(action)

    def _activation_progress_check(self, action):
        if self._ctx.is_cancelled():
            self._activation_clean_up()
            return
        devname = self._nm_dev.get_iface()
        cur_nm_dev = self._ctx.get_nm_dev(devname)
        if cur_nm_dev and cur_nm_dev != self._nm_dev:
            logging.debug(f"The NM.Device of profile {devname} changed")
            self._remove_dev_handlers()
            self._nm_dev = cur_nm_dev
            self.wait_dev_activation(action)

        cur_nm_ac = get_device_active_connection(self.nmdevice)
        if cur_nm_ac and cur_nm_ac != self._nm_ac:
            logging.debug(
                "Active connection of device {} has been replaced".format(
                    self.devname
                )
            )
            self._remove_ac_handlers()
            self._nm_ac = cur_nm_ac
            self._wait_ac_activation(action)
        if is_activated(self._nm_ac, self._nm_dev):
            logging.debug(
                "Connection activation succeeded: dev=%s, con-state=%s, "
                "dev-state=%s, state-flags=%s",
                devname,
                self._nm_ac.get_state(),
                self._nm_dev.get_state(),
                self._nm_ac.get_state_flags(),
            )
            self._activation_clean_up()
            self._ctx.finish_async(action)
        elif not self._is_activating():
            reason = f"{self._nm_ac.get_state_reason()}"
            if self.nmdevice:
                reason += f" {self.nmdevice.get_state_reason()}"
            self._activation_clean_up()
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed: reason={reason}")
            )

    def _activation_clean_up(self):
        self._remove_ac_handlers()
        self._remove_dev_handlers()

    def _is_activating(self):
        if not self._nm_ac or not self._nm_dev:
            return True
        if (
            self._nm_dev.get_state_reason()
            == NM.DeviceStateReason.NEW_ACTIVATION
        ):
            return True

        return (
            self._nm_ac.get_state() == NM.ActiveConnectionState.ACTIVATING
        ) and not is_activated(self._nm_ac, self._nm_dev)

    def _remove_dev_handlers(self):
        for handler_id in self._dev_handlers:
            self._nm_dev.handler_disconnect(handler_id)
        self._dev_handlers = set()

    def _remove_ac_handlers(self):
        for handler_id in self._ac_handlers:
            self._nm_ac.handler_disconnect(handler_id)
        self._ac_handlers = set()

    def _add_connection2_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
        try:
            profile = src_object.add_connection2_finish(result)[0]
        except Exception as e:
            self._ctx.fail(
                NmstateLibnmError(f"{action} failed with error: {e}")
            )
            return

        if profile is None:
            self._ctx.fail(
                NmstateLibnmError(
                    f"{action} failed with error: 'None returned from "
                    "add_connection2_finish()"
                )
            )
        else:
            self._ctx.finish_async(action)

    def _update2_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
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

    def _delete_connection_callback(self, src_object, result, user_data):
        if self._ctx.is_cancelled():
            return
        action = user_data
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
                    f"{action} failed: "
                    "error='None returned from delete_finish()'"
                )
            )

    def _reset_profile(self):
        self._con_profile = None


class ConnectionSetting:
    def __init__(self, con_setting=None):
        self._setting = con_setting

    def create(self, con_name, iface_name, iface_type):
        con_setting = NM.SettingConnection.new()
        con_setting.props.id = con_name
        con_setting.props.interface_name = iface_name
        con_setting.props.uuid = str(uuid.uuid4())
        con_setting.props.type = iface_type
        con_setting.props.autoconnect = True
        con_setting.props.autoconnect_slaves = (
            NM.SettingConnectionAutoconnectSlaves.YES
        )

        self._setting = con_setting

    def import_by_profile(self, con_profile):
        base = con_profile.profile.get_setting_connection()
        new = NM.SettingConnection.new()
        new.props.id = base.props.id
        new.props.interface_name = base.props.interface_name
        new.props.uuid = base.props.uuid
        new.props.type = base.props.type
        new.props.autoconnect = True
        new.props.autoconnect_slaves = base.props.autoconnect_slaves

        self._setting = new

    def set_master(self, master, slave_type):
        if master is not None:
            self._setting.props.master = master
            self._setting.props.slave_type = slave_type

    def set_profile_name(self, con_name):
        self._setting.props.id = con_name

    @property
    def setting(self):
        return self._setting


def get_device_active_connection(nm_device):
    active_conn = None
    if nm_device:
        active_conn = nm_device.get_active_connection()
    return active_conn


def delete_iface_inactive_connections(context, ifname):
    for con in list_connections_by_ifname(context, ifname):
        con.delete()


def list_connections_by_ifname(context, ifname):
    return [
        ConnectionProfile(context, profile=con)
        for con in context.client.get_connections()
        if con.get_interface_name() == ifname
    ]


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
            #   * Is master device.
            #   * DHCPv4 enabled with IP6_READY flag.
            #   * DHCPv6/Autoconf with IP4_READY flag.
            #   * DHCPv4 enabled with DHCPv6/Autoconf enabled.
            return (
                NM.DeviceState.IP_CONFIG
                <= nm_dev.get_state()
                <= NM.DeviceState.ACTIVATED
            )

    return False
