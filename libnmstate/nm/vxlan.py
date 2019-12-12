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

from distutils.version import StrictVersion

from libnmstate import nm
from libnmstate.nm import connection
from libnmstate.nm import nmclient
from libnmstate.schema import VXLAN


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
        vxlan_setting = nmclient.NM.SettingVxlan.new()

    vxlan_setting.props.id = vxlan[VXLAN.ID]
    vxlan_setting.props.parent = vxlan[VXLAN.BASE_IFACE]
    vxlan_remote = vxlan.get(VXLAN.REMOTE)
    if vxlan_remote:
        vxlan_setting.props.remote = vxlan_remote
    vxlan_destination_port = vxlan.get(VXLAN.DESTINATION_PORT)
    if vxlan_destination_port:
        vxlan_setting.props.destination_port = vxlan_destination_port

    return vxlan_setting


def get_info(device):
    """
    Provides the current active values for a device
    """
    if device.get_device_type() == nmclient.NM.DeviceType.VXLAN:
        base_iface = ""
        if device.props.parent:
            base_iface = device.props.parent.get_iface()
        remote = device.props.group
        if not remote:
            remote = ""
        return {
            VXLAN.CONFIG_SUBTREE: {
                VXLAN.ID: device.props.id,
                VXLAN.BASE_IFACE: base_iface,
                VXLAN.REMOTE: remote,
                VXLAN.DESTINATION_PORT: _get_destination_port(device),
            }
        }
    return {}


def _get_destination_port(device):
    """
    Retrieve the destination port.

    The destination port is retrieved from the profile settings instead
    of the device (which represents the kernel state)
    due to an existing issue [1].

    [1] https://bugzilla.redhat.com/show_bug.cgi?id=1768388
    """
    if nm.nmclient.nm_version() >= StrictVersion("1.20.6"):
        return device.get_dst_port()
    else:
        con = connection.ConnectionProfile()
        con.import_by_device(device)
        if con.profile:
            vxlan_settings = con.profile.get_setting_vxlan()
            if vxlan_settings:
                return vxlan_settings.get_destination_port()
    return 0
