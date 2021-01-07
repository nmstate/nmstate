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

from libnmstate.schema import VRF
from .common import NM


def create_vrf_setting(vrf_config):
    vrf_setting = NM.SettingVrf.new()
    vrf_setting.props.table = vrf_config[VRF.ROUTE_TABLE_ID]
    return vrf_setting


def get_vrf_config(nm_profile, subordinate_nm_profiles):
    nm_setting = nm_profile.get_setting_by_name(NM.SETTING_VRF_SETTING_NAME)
    if nm_setting:
        return {
            VRF.PORT_SUBTREE: [
                port_profile.get_interface_name()
                for port_profile in subordinate_nm_profiles
            ],
            VRF.ROUTE_TABLE_ID: nm_setting.props.table,
        }
    return {}
