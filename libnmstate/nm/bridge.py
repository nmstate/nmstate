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

import six

from libnmstate.nm import connection
from libnmstate.nm import nmclient
from libnmstate.schema import LinuxBridge as LB


BRIDGE_TYPE = 'bridge'


def create_setting(options, base_con_profile):
    bridge_setting = _get_current_bridge_setting(base_con_profile)
    if not bridge_setting:
        bridge_setting = nmclient.NM.SettingBridge.new()

    if options:
        _set_bridge_properties(bridge_setting, options)

    return bridge_setting


def _get_current_bridge_setting(base_con_profile):
    bridge_setting = None
    if base_con_profile:
        bridge_setting = base_con_profile.get_setting_bridge()
        if bridge_setting:
            bridge_setting = bridge_setting.duplicate()
    return bridge_setting


def _set_bridge_properties(bridge_setting, options):
    for key, val in six.viewitems(options):
        if key == LB.MAC_AGEING_TIME:
            bridge_setting.props.ageing_time = val
        elif key == LB.GROUP_FORWARD_MASK:
            bridge_setting.props.group_forward_mask = val
        elif key == LB.MULTICAST_SNOOPING:
            bridge_setting.props.multicast_snooping = val
        elif key == LB.STP_SUBTREE:
            _set_bridge_stp_properties(bridge_setting, val)
        elif key == LB.VLAN_FILTERING:
            bridge_setting.props.vlan_filtering = val
            bridge_setting.props.vlan_default_pvid = 0
        elif key == LB.VLANS:
            for vlan_data in val:
                bridge_setting.add_vlan(_build_vlan_bridge(vlan_data))


def _set_bridge_stp_properties(bridge_setting, bridge_stp):
    bridge_setting.props.stp = bridge_stp[LB.STP_ENABLED]
    if bridge_stp[LB.STP_ENABLED] is True:
        for stp_key, stp_val in six.viewitems(bridge_stp):
            if stp_key == LB.STP_PRIORITY:
                bridge_setting.props.priority = stp_val
            elif stp_key == LB.STP_FORWARD_DELAY:
                bridge_setting.props.forward_delay = stp_val
            elif stp_key == LB.STP_HELLO_TIME:
                bridge_setting.props.hello_time = stp_val
            elif stp_key == LB.STP_MAX_AGE:
                bridge_setting.props.max_age = stp_val


def _build_vlan_bridge(vlan_config):
    vlan_range_min = vlan_config['vlan-range-min']
    vlan_range_max = vlan_config.get('vlan-range-max')
    pvid = vlan_config.get('pvid', False)
    untagged = vlan_config.get('untagged', False)
    bridge_vlan = nmclient.NM.BridgeVlan.new(
        vlan_range_min, vlan_range_max or vlan_range_min
    )
    bridge_vlan.set_untagged(untagged)
    if pvid:
        bridge_vlan.set_pvid(vlan_range_max or vlan_range_min)
    return bridge_vlan


def create_port_setting(options, base_con_profile):
    port_setting = None
    if base_con_profile:
        port_setting = base_con_profile.get_setting_bridge_port()
        if port_setting:
            port_setting = port_setting.duplicate()

    if not port_setting:
        port_setting = nmclient.NM.SettingBridgePort.new()

    for key, val in six.viewitems(options):
        if key == LB.PORT_STP_PRIORITY:
            port_setting.props.priority = val
        elif key == LB.PORT_STP_HAIRPIN_MODE:
            port_setting.props.hairpin_mode = val
        elif key == LB.PORT_STP_PATH_COST:
            port_setting.props.path_cost = val
        elif key == LB.PORT_VLANS:
            for vlan_data in val:
                port_setting.add_vlan(_build_vlan_bridge(vlan_data))

    return port_setting


def get_info(nmdev):
    """
    Provides the current active values for a device
    """
    info = {}
    if nmdev.get_device_type() != nmclient.NM.DeviceType.BRIDGE:
        return info
    bridge_setting = _get_bridge_setting(nmdev)
    if not bridge_setting:
        return info

    port_profiles = _get_slave_profiles(nmdev)
    info[LB.CONFIG_SUBTREE] = {
        LB.PORT_SUBTREE: _get_bridge_ports_info(port_profiles),
        LB.OPTIONS_SUBTREE: {
            LB.MAC_AGEING_TIME: bridge_setting.props.ageing_time,
            LB.GROUP_FORWARD_MASK: bridge_setting.props.group_forward_mask,
            LB.MULTICAST_SNOOPING: bridge_setting.props.multicast_snooping,
            LB.STP_SUBTREE: {
                LB.STP_ENABLED: bridge_setting.props.stp,
                LB.STP_PRIORITY: bridge_setting.props.priority,
                LB.STP_FORWARD_DELAY: bridge_setting.props.forward_delay,
                LB.STP_HELLO_TIME: bridge_setting.props.hello_time,
                LB.STP_MAX_AGE: bridge_setting.props.max_age,
            },
            LB.VLAN_FILTERING: bridge_setting.props.vlan_filtering,
            LB.VLANS: [
                _get_vlan_info(bridge_vlan)
                for bridge_vlan in bridge_setting.props.vlans
            ],
        },
    }
    return info


def get_slaves(nm_device):
    return nm_device.get_slaves()


def _get_bridge_setting(nmdev):
    bridge_setting = None
    bridge_con_profile = connection.ConnectionProfile()
    bridge_con_profile.import_by_device(nmdev)
    if bridge_con_profile.profile:
        bridge_setting = bridge_con_profile.profile.get_setting_bridge()
    return bridge_setting


def _get_bridge_ports_info(port_profiles):
    ports_info = []
    for p in port_profiles:
        port_info = _get_bridge_port_info(p)
        if port_info:
            ports_info.append(port_info)
    return ports_info


def _get_bridge_port_info(port_profile):
    """Report port information."""

    port_setting = port_profile.get_setting_bridge_port()
    return {
        LB.PORT_NAME: port_profile.get_interface_name(),
        LB.PORT_STP_PRIORITY: port_setting.props.priority,
        LB.PORT_STP_HAIRPIN_MODE: port_setting.props.hairpin_mode,
        LB.PORT_STP_PATH_COST: port_setting.props.path_cost,
        LB.PORT_VLANS: [
            _get_vlan_info(port_vlan) for port_vlan in port_setting.props.vlans
        ],
    }


def _get_slave_profiles(master_device):
    slave_profiles = []
    for dev in master_device.get_slaves():
        active_con = connection.get_device_active_connection(dev)
        if active_con:
            slave_profiles.append(active_con.props.connection)
    return slave_profiles


def _get_vlan_info(port_vlan_info):
    vlan_min, vlan_max = _get_vlan_ranges(port_vlan_info.to_str())
    port_data = {'vlan-range-min': vlan_min}
    if vlan_max != vlan_min:
        port_data['vlan-range-max'] = vlan_max
    if port_vlan_info.is_pvid():
        port_data['pvid'] = True
    if port_vlan_info.is_untagged():
        port_data['untagged'] = True
    return port_data


def _get_vlan_ranges(vlan_string_repr):
    if 'untagged' in vlan_string_repr or 'pvid' in vlan_string_repr:
        vlan_data = vlan_string_repr[: vlan_string_repr.find(' ')]
    else:
        vlan_data = vlan_string_repr
    if '-' in vlan_data:
        vlan_min, vlan_max = vlan_data.split('-')
        return int(vlan_min), int(vlan_max)
    else:
        return int(vlan_data), int(vlan_data)
