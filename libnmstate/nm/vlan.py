#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

from libnmstate.schema import VLAN
from .common import NM


def create_setting(iface_state, base_con_profile):
    vlan = iface_state.get(VLAN.TYPE)
    if not vlan:
        return None

    vlan_id = vlan[VLAN.ID]
    vlan_base_iface = vlan[VLAN.BASE_IFACE]

    vlan_setting = None
    if base_con_profile:
        vlan_setting = base_con_profile.get_setting_vlan()
        if vlan_setting:
            vlan_setting = vlan_setting.duplicate()

    if not vlan_setting:
        vlan_setting = NM.SettingVlan.new()

    vlan_setting.props.id = vlan_id
    vlan_setting.props.parent = vlan_base_iface

    return vlan_setting
