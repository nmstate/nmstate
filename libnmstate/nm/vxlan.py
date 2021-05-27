#
# Copyright (c) 2019 Red Hat, Inc.
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

from libnmstate.schema import VXLAN
from .common import NM


def create_setting(iface_state, base_con_profile):
    vxlan = iface_state.get(VXLAN.CONFIG_SUBTREE)
    if not vxlan:
        return None

    vxlan_setting = None
    if base_con_profile:
        vxlan_setting = base_con_profile.get_setting_vxlan()
        if vxlan_setting:
            vxlan_setting = vxlan_setting.duplicate()

    if not vxlan_setting:
        vxlan_setting = NM.SettingVxlan.new()

    vxlan_setting.props.id = vxlan[VXLAN.ID]
    vxlan_base_if = vxlan.get(VXLAN.BASE_IFACE)
    if vxlan_base_if:
        vxlan_setting.props.parent = vxlan_base_if
    vxlan_learning = vxlan.get(VXLAN.LEARNING)
    if vxlan_learning:
        vxlan_setting.props.learning = vxlan_learning
    vxlan_local = vxlan.get(VXLAN.LOCAL)
    vxlan_setting.props.local = vxlan_local if vxlan_local else None
    vxlan_remote = vxlan.get(VXLAN.REMOTE)
    vxlan_setting.props.remote = vxlan_remote if vxlan_remote else None
    vxlan_destination_port = vxlan.get(VXLAN.DESTINATION_PORT)
    if vxlan_destination_port:
        vxlan_setting.props.destination_port = vxlan_destination_port

    return vxlan_setting
