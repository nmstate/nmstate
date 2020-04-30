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
import time
import uuid

from . import mainloop as nm_mainloop
from .active_connection import ActiveConnection
from .common import NM
from .common import GLib


class ConnectionProfile:
    def __init__(self, client, profile=None):
        self._client = client
        self._con_profile = profile
        self._mainloop = nm_mainloop.mainloop()
        self._nmdevice = None
        self._con_id = None

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
            self.profile = self._client.get_connection_by_id(self.con_id)

    def update(self, con_profile):
        user_data = con_profile.profile.get_interface_name()
        flags = NM.SettingsUpdate2Flags.BLOCK_AUTOCONNECT
        flags |= NM.SettingsUpdate2Flags.TO_DISK
        args = None

        self._mainloop.push_action(
            self.profile.update2,
            con_profile.profile.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            self._mainloop.cancellable,
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

        user_data = None
        args = None
        ignore_out_result = False  # Don't fall back to old AddConnection()
        self._mainloop.push_action(
            self._client.add_connection2,
            self.profile.to_dbus(NM.ConnectionSerializationFlags.ALL),
            flags,
            args,
            ignore_out_result,
            self._mainloop.cancellable,
            self._add_connection2_callback,
            user_data,
        )

    def delete(self):
        self._mainloop.push_action(self._safe_delete_async)

    def _safe_delete_async(self):
        if not self.profile:
            self.import_by_id()
            if not self.profile:
                self.import_by_device()
        if not self.profile:
            # No callback is expected, so we should call the next one.
            self._mainloop.execute_next_action()
            return

        user_data = None
        self.profile.delete_async(
            self._mainloop.cancellable,
            self._delete_connection_callback,
            user_data,
        )

    def activate(self):
        self._mainloop.push_action(self.safe_activate_async)

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
        return self._nmdevice

    @nmdevice.setter
    def nmdevice(self, dev):
        assert self._nmdevice is None
        self._nmdevice = dev

    @property
    def con_id(self):
        con_id = self._con_profile.get_id() if self._con_profile else None
        return self._con_id or con_id

    @con_id.setter
    def con_id(self, connection_id):
        assert self._con_id is None
        self._con_id = connection_id

    def safe_activate_async(self):
        if self.con_id:
            self.import_by_id()
        elif self.nmdevice:
            self.import_by_device()
        elif not self.profile:
            err_format = "Missing base properties: profile={}, id={}, dev={}"
            err_msg = err_format.format(
                self.profile, self.con_id, self.devname
            )
            self._mainloop.quit(err_msg)

        cancellable = self._mainloop.new_cancellable()

        specific_object = None
        user_data = cancellable
        self._client.activate_connection_async(
            self.profile,
            self.nmdevice,
            specific_object,
            cancellable,
            self._active_connection_callback,
            user_data,
        )

    def get_setting_duplicate(self, setting_name):
        setting = None
        if self.profile:
            setting = self.profile.get_setting_by_name(setting_name)
            if setting:
                setting = setting.duplicate()
        return setting

    def _active_connection_callback(self, src_object, result, user_data):
        cancellable = user_data
        self._mainloop.drop_cancellable(cancellable)

        try:
            nm_act_con = src_object.activate_connection_finish(result)
        except Exception as e:
            act_type, act_object = self._get_activation_metadata()

            if self._mainloop.is_action_canceled(e):
                logging.debug(
                    "Connection activation canceled on %s %s: error=%s",
                    act_type,
                    act_object,
                    e,
                )
            elif self._is_connection_unavailable(e):
                logging.warning(
                    "Connection unavailable on %s %s, retrying",
                    act_type,
                    act_object,
                )
                self._reset_profile()
                time.sleep(0.1)
                self.safe_activate_async()
            else:
                self._mainloop.quit(
                    "Connection activation failed on {} {}: error={}".format(
                        act_type, act_object, e
                    )
                )
            return

        if nm_act_con is None:
            act_type, act_object = self._get_activation_metadata()
            self._mainloop.quit(
                "Connection activation failed on {} {}: error=unknown".format(
                    act_type, act_object
                )
            )
        else:
            devname = nm_act_con.props.connection.get_interface_name()
            logging.debug(
                "Connection activation initiated: dev=%s, con-state=%s",
                devname,
                nm_act_con.props.state,
            )

            ac = ActiveConnection(self._client, nm_act_con)
            if ac.is_active:
                self._mainloop.execute_next_action()
            elif ac.is_activating:
                self.waitfor_active_connection_async(ac)
            else:
                self._mainloop.quit(
                    "Connection activation failed on {}: reason={}".format(
                        devname, ac.reason
                    )
                )

    @staticmethod
    def _is_connection_unavailable(err):
        return (
            isinstance(err, GLib.GError)
            and err.domain == "nm-manager-error-quark"
            and err.code == 2
            and "is not available on the device" in err.message
        )

    def _get_activation_metadata(self):
        if self._nmdevice:
            activation_type = "device"
            activation_object = self._nmdevice.get_iface()
        elif self._con_id:
            activation_type = "connection_id"
            activation_object = self._con_id
        else:
            activation_type = activation_object = "unknown"

        return activation_type, activation_object

    def waitfor_active_connection_async(self, ac):
        ac.handlers.add(
            ac.nm_active_connection.connect(
                "state-changed", self._waitfor_active_connection_callback, ac
            )
        )
        ac.handlers.add(
            ac.nm_active_connection.connect(
                "notify::state-flags",
                self._waitfor_state_flags_change_callback,
                ac,
            )
        )
        ac.device_handlers.add(
            ac.nmdevice.connect(
                "state-changed", self._waitfor_device_state_change_callback, ac
            )
        )

    def _waitfor_device_state_change_callback(
        self, _dev, _new_state, _old_state, _reason, ac
    ):
        self._waitfor_active_connection_callback(None, None, None, ac)

    def _waitfor_state_flags_change_callback(self, _nm_act_con, _state, ac):
        self._waitfor_active_connection_callback(None, None, None, ac)

    def _waitfor_active_connection_callback(
        self, _nm_act_con, _state, _reason, ac
    ):
        cur_nm_act_conn = get_device_active_connection(self.nmdevice)
        if cur_nm_act_conn and cur_nm_act_conn != ac.nm_active_connection:
            logging.debug(
                "Active connection of device {} has been replaced".format(
                    self.devname
                )
            )
            ac.remove_handlers()
            ac = ActiveConnection(self._client)
            # Don't rely on the first device of
            # NM.ActiveConnection.get_devices() but set explicitly.
            ac.import_by_device(self.nmdevice)
            self.waitfor_active_connection_async(ac)
        if ac.is_active:
            logging.debug(
                "Connection activation succeeded: dev=%s, con-state=%s, "
                "dev-state=%s, state-flags=%s",
                ac.devname,
                ac.state,
                ac.nmdev_state,
                ac.nm_active_connection.get_state_flags(),
            )
            ac.remove_handlers()
            self._mainloop.execute_next_action()
        elif (
            not ac.is_activating
            and self._is_sriov_parameter_not_supported_by_driver()
        ):
            ac.remove_handlers()
            self._mainloop.quit(
                f"The device={self.devname} does not support one or more "
                "of the SR-IOV parameters set."
            )
        elif not ac.is_activating:
            ac.remove_handlers()
            self._mainloop.quit(
                "Connection activation failed on {}: reason={}".format(
                    ac.devname, ac.reason
                )
            )

    def _is_sriov_parameter_not_supported_by_driver(self):
        return (
            self._nmdevice.props.state_reason
            == NM.DeviceStateReason.SRIOV_CONFIGURATION_FAILED
        )

    def _add_connection2_callback(self, src_object, result, _user_data):
        try:
            profile = src_object.add_connection2_finish(result)[0]
        except Exception as e:
            if self._mainloop.is_action_canceled(e):
                logging.debug("Connection adding canceled: error=%s", e)
            else:
                self._mainloop.quit(
                    "Connection adding failed: error={}".format(e)
                )
            return

        if profile is None:
            self._mainloop.quit("Connection adding failed: error=unknown")
        else:
            devname = profile.get_interface_name()
            logging.debug("Connection adding succeeded: dev=%s", devname)
            self._mainloop.execute_next_action()

    def _update2_callback(self, src_object, result, user_data):
        iface_name = user_data
        try:
            ret = src_object.update2_finish(result)
        except Exception as e:
            if self._mainloop.is_action_canceled(e):
                logging.debug(
                    "Connection update canceled: dev=%s, error=%s",
                    iface_name,
                    e,
                )
            else:
                self._mainloop.quit(
                    "Connection update failed: dev={} error={}".format(
                        iface_name, e
                    )
                )
            return

        if ret is None:
            self._mainloop.quit(
                "Connection update failed: dev={} unknown error".format(
                    iface_name
                )
            )
            return

        logging.debug("Connection update succeeded: dev=%s", iface_name)
        self._mainloop.execute_next_action()

    def _delete_connection_callback(self, src_object, result, user_data):
        try:
            success = src_object.delete_finish(result)
        except Exception as e:
            if self.nmdevice:
                target = "dev/" + str(self.nmdevice.get_iface())
            else:
                target = "con/" + str(self.con_id)

            if self._mainloop.is_action_canceled(e):
                logging.debug(
                    "Connection deletion aborted on %s: error=%s", target, e
                )
            else:
                self._mainloop.quit(
                    "Connection deletion failed on {}: error={}".format(
                        target, e
                    )
                )
            return

        devname = src_object.get_interface_name()
        if success:
            logging.debug("Connection deletion succeeded: dev=%s", devname)
            self._mainloop.execute_next_action()
        else:
            self._mainloop.quit(
                "Connection deletion failed: "
                "dev={}, error=unknown".format(devname)
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

    @property
    def setting(self):
        return self._setting


def get_device_active_connection(nm_device):
    active_conn = None
    if nm_device:
        active_conn = nm_device.get_active_connection()
    return active_conn


def delete_iface_inactive_connections(nm_client, ifname):
    for con in list_connections_by_ifname(nm_client, ifname):
        con.delete()


def list_connections_by_ifname(nm_client, ifname):
    return [
        ConnectionProfile(nm_client, profile=con)
        for con in nm_client.get_connections()
        if con.get_interface_name() == ifname
    ]
