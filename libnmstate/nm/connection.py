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

import uuid

from .common import NM


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

    def import_by_profile(self, profile):
        base = profile.get_setting_connection()
        new = NM.SettingConnection.new()
        new.props.id = base.props.id
        new.props.interface_name = base.props.interface_name
        new.props.uuid = base.props.uuid
        new.props.type = base.props.type
        new.props.autoconnect = True
        new.props.autoconnect_slaves = base.props.autoconnect_slaves

        self._setting = new

    def set_controller(self, controller, port_type):
        if controller is not None:
            self._setting.props.master = controller
            self._setting.props.slave_type = port_type

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


def list_connections_by_ifname(context, ifname):
    return [
        con
        for con in context.client.get_connections()
        if con.get_interface_name() == ifname
    ]


def create_new_simple_connection(settings):
    simple_conn = NM.SimpleConnection.new()
    for setting in settings:
        simple_conn.add_setting(setting)

    return simple_conn
