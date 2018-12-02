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

import six

from libnmstate.nm import connection
from libnmstate.nm import nmclient
from libnmstate.schema import LinuxBridge as LB


BRIDGE_TYPE = LB.TYPE


def create_setting(iface_state, base_con_profile):
    bridge_conf = iface_state.get(LB.CONFIG_SUBTREE)
    if not bridge_conf:
        return None

    bridge_setting = _get_current_bridge_setting(base_con_profile)
    if not bridge_setting:
        bridge_setting = nmclient.NM.SettingBridge.new()

    _set_bridge_properties(bridge_setting, bridge_conf)

    return bridge_setting


def _get_current_bridge_setting(base_con_profile):
    bridge_setting = None
    if base_con_profile:
        bridge_setting = base_con_profile.get_setting_bridge()
        if bridge_setting:
            bridge_setting = bridge_setting.duplicate()
    return bridge_setting


def _set_bridge_properties(bridge_setting, bridge_conf):
    for key, val in six.viewitems(bridge_conf):
        if key == LB.MAC_AGEING_TIME:
            bridge_setting.props.ageing_time = val
        elif key == LB.GROUP_FORWARD_MASK:
            bridge_setting.props.group_forward_mask = val
        elif key == LB.MULTICAST_SNOOPING:
            bridge_setting.props.multicast_snooping = val
        elif key == LB.STP_SUBTREE:
            _set_bridge_stp_properties(bridge_setting, val)


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


def create_port_setting(options, base_con_profile):
    port_setting = None
    if base_con_profile:
        port_setting = base_con_profile.get_setting_bridge_port()
        if port_setting:
            port_setting = port_setting.duplicate()

    if not port_setting:
        port_setting = nmclient.NM.SettingBridgePort.new()

    port_setting.props.priority = options[LB.PORT_STP_PRIORITY]
    port_setting.props.hairpin_mode = options[LB.PORT_STP_HAIRPIN_MODE]
    port_setting.props.path_cost = options[LB.PORT_STP_PATH_COST]

    return port_setting


def get_info(nmdev):
    """
    Provides the current active values for a device
    """
    info = {}
    if nmdev.get_device_type() == nmclient.NM.DeviceType.BRIDGE:
        bridge_setting = _get_bridge_setting(nmdev)
        if bridge_setting:
            port_profiles = _get_slave_profiles(nmdev)
            info[LB.CONFIG_SUBTREE] = {
                LB.PORT_SUBTREE: _get_bridge_ports_info(port_profiles),
                LB.MAC_AGEING_TIME: bridge_setting.props.ageing_time,
                LB.GROUP_FORWARD_MASK: bridge_setting.props.group_forward_mask,
                LB.MULTICAST_SNOOPING: bridge_setting.props.multicast_snooping,
                LB.STP_SUBTREE: {
                    LB.STP_ENABLED: bridge_setting.props.stp,
                    LB.STP_PRIORITY: bridge_setting.props.priority,
                    LB.STP_FORWARD_DELAY: bridge_setting.props.forward_delay,
                    LB.STP_HELLO_TIME: bridge_setting.props.hello_time,
                    LB.STP_MAX_AGE: bridge_setting.props.max_age
                }
            }
    return info


def _get_bridge_setting(nmdev):
    bridge_setting = None
    bridge_profile = connection.get_device_connection(nmdev)
    if bridge_profile:
        bridge_setting = bridge_profile.get_setting_bridge()
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
    }


def _get_slave_profiles(master_device):
    slave_profiles = []
    for dev in master_device.get_slaves():
        active_con = connection.get_device_active_connection(dev)
        if active_con:
            slave_profiles.append(active_con.props.connection)
    return slave_profiles
