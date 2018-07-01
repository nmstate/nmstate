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

from libnmstate import nmclient

from . import connection
from . import device


def is_ovs_bridge_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.OVS_BRIDGE


def is_ovs_port_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.OVS_PORT


def is_ovs_interface_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.OVS_INTERFACE


def get_ovs_info(bridge_device, devices_info):
    port_profiles = _get_slave_profiles(bridge_device, devices_info)

    return {
        'port': _get_bridge_ports_info(port_profiles, devices_info),
        'options': _get_bridge_options(bridge_device)
    }


def _get_bridge_ports_info(port_profiles, devices_info):
    ports_info = []
    for p in port_profiles:
        port_info = _get_bridge_port_info(p, devices_info)
        if port_info:
            ports_info.append(port_info)
    return ports_info


def _get_bridge_port_info(port_profile, devices_info):
    """
    Report port information.
    Note: The current implementation supports only system OVS ports and
    access vlan-mode (trunks are not supported).
    """
    port_info = {}

    port_setting = port_profile.get_setting(nmclient.NM.SettingOvsPort)
    vlan_mode = port_setting.props.vlan_mode

    port_name = port_profile.get_interface_name()
    port_device = device.get_device_by_name(port_name)
    port_slave_profiles = _get_slave_profiles(port_device, devices_info)
    port_slave_names = [c.get_interface_name() for c in port_slave_profiles]

    if port_slave_names:
        port_info['name'] = port_slave_names[0]
        port_info['type'] = 'system'
        if vlan_mode:
            port_info['vlan-mode'] = vlan_mode
            port_info['access-tag'] = port_setting.props.tag

    return port_info


def _get_bridge_options(bridge_device):
    bridge_options = {}
    con = connection.get_device_connection(bridge_device)
    if con:
        bridge_setting = con.get_setting(nmclient.NM.SettingOvsBridge)
        bridge_options['stp'] = bridge_setting.props.stp_enable
        bridge_options['rstp'] = bridge_setting.props.rstp_enable
        bridge_options['fail-mode'] = bridge_setting.props.fail_mode or ''
        bridge_options['mcast-snooping-enable'] = (
            bridge_setting.props.mcast_snooping_enable)

    return bridge_options


def _get_slave_profiles(master_device, devices_info):
    slave_profiles = []
    for dev, _ in devices_info:
        active_con = connection.get_device_active_connection(dev)
        if active_con:
            master = active_con.props.master
            if master == master_device:
                slave_profiles.append(active_con.props.connection)
    return slave_profiles
