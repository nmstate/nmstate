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

from .common import NM


def create_vrf_setting(vrf_iface):
    vrf_setting = NM.SettingVrf.new()
    vrf_setting.props.table = vrf_iface.route_table_id
    return vrf_setting


def is_vrf_table_id_changed(vrf_iface, nm_dev):
    return vrf_iface.route_table_id != nm_dev.props.table
