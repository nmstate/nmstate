#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from libnmstate.nm import nmclient


VLAN_TYPE = 'vlan'


def create_setting(iface_state, base_con_profile):
    vlan = iface_state.get(VLAN_TYPE)
    if not vlan:
        return None

    vlan_id = vlan['id']
    vlan_base_iface = vlan['base-iface']

    vlan_setting = None
    if base_con_profile:
        vlan_setting = base_con_profile.get_setting_vlan()
        if vlan_setting:
            vlan_setting = vlan_setting.duplicate()

    if not vlan_setting:
        vlan_setting = nmclient.NM.SettingVlan.new()

    vlan_setting.props.id = vlan_id
    vlan_setting.props.parent = vlan_base_iface

    return vlan_setting


def get_info(device):
    """
    Provides the current active values for a device
    """
    info = {}
    if device.get_device_type() == nmclient.NM.DeviceType.VLAN:
        info['vlan'] = {
            'id': device.props.vlan_id,
            'base-iface': device.props.parent.get_iface()
        }
    return info
