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

from libnmstate.schema import LinuxBridge as LB

from .bridge_port_vlan import nmstate_port_vlan_to_nm
from .bridge_port_vlan import get_linux_bridge_port_vlan_config
from .common import NM


BRIDGE_TYPE = "bridge"

OPT = LB.Options

NM_BRIDGE_OPTIONS_MAP = {
    OPT.GROUP_ADDR: "group_address",
    OPT.HASH_MAX: "multicast_hash_max",
    OPT.MULTICAST_LAST_MEMBER_COUNT: "multicast_last_member_count",
    OPT.MULTICAST_LAST_MEMBER_INTERVAL: "multicast_last_member_interval",
    OPT.MULTICAST_MEMBERSHIP_INTERVAL: "multicast_membership_interval",
    OPT.MULTICAST_QUERIER: "multicast_querier",
    OPT.MULTICAST_QUERIER_INTERVAL: "multicast_querier_interval",
    OPT.MULTICAST_QUERY_USE_IFADDR: "multicast_query_use_ifaddr",
    OPT.MULTICAST_QUERY_INTERVAL: "multicast_query_interval",
    OPT.MULTICAST_QUERY_RESPONSE_INTERVAL: "multicast_query_response_interval",
    OPT.MULTICAST_STARTUP_QUERY_COUNT: "multicast_startup_query_count",
    OPT.MULTICAST_STARTUP_QUERY_INTERVAL: "multicast_startup_query_interval",
}


def create_setting(
    bridge_state, base_con_profile, original_desired_iface_state
):
    options = original_desired_iface_state.get(LB.CONFIG_SUBTREE, {}).get(
        LB.OPTIONS_SUBTREE
    )
    bridge_setting = _get_current_bridge_setting(base_con_profile)
    if not bridge_setting:
        bridge_setting = NM.SettingBridge.new()

    if options:
        _set_bridge_properties(bridge_setting, options)

    bridge_setting.props.vlan_filtering = _is_vlan_filter_active(bridge_state)

    return bridge_setting


def _get_current_bridge_setting(base_con_profile):
    bridge_setting = None
    if base_con_profile:
        bridge_setting = base_con_profile.get_setting_bridge()
        if bridge_setting:
            bridge_setting = bridge_setting.duplicate()
    return bridge_setting


def _set_bridge_properties(bridge_setting, options):
    for key, val in options.items():
        if key == LB.Options.MAC_AGEING_TIME:
            bridge_setting.props.ageing_time = val
        elif key == LB.Options.GROUP_FORWARD_MASK:
            bridge_setting.props.group_forward_mask = val
        elif key == LB.Options.MULTICAST_SNOOPING:
            bridge_setting.props.multicast_snooping = val
        elif key == LB.STP_SUBTREE:
            _set_bridge_stp_properties(bridge_setting, val)
        elif key in NM_BRIDGE_OPTIONS_MAP:
            nm_prop_name = NM_BRIDGE_OPTIONS_MAP[key]
            # NM is using the sysfs name
            if key == LB.Options.GROUP_ADDR:
                val = val.lower()
            setattr(bridge_setting.props, nm_prop_name, val)


def _set_bridge_stp_properties(bridge_setting, bridge_stp):
    bridge_setting.props.stp = bridge_stp[LB.STP.ENABLED]
    if bridge_stp[LB.STP.ENABLED] is True:
        for stp_key, stp_val in bridge_stp.items():
            if stp_key == LB.STP.PRIORITY:
                bridge_setting.props.priority = stp_val
            elif stp_key == LB.STP.FORWARD_DELAY:
                bridge_setting.props.forward_delay = stp_val
            elif stp_key == LB.STP.HELLO_TIME:
                bridge_setting.props.hello_time = stp_val
            elif stp_key == LB.STP.MAX_AGE:
                bridge_setting.props.max_age = stp_val


def _is_vlan_filter_active(bridge_state):
    return any(
        port.get(LB.Port.VLAN_SUBTREE, {}) != {}
        for port in bridge_state.get(LB.CONFIG_SUBTREE, {}).get(
            LB.PORT_SUBTREE, []
        )
    )


def create_port_setting(options, base_con_profile):
    port_setting = None
    if base_con_profile:
        port_setting = base_con_profile.get_setting_bridge_port()
        if port_setting:
            port_setting = port_setting.duplicate()

    if not port_setting:
        port_setting = NM.SettingBridgePort.new()

    for key, val in options.items():
        if key == LB.Port.STP_PRIORITY:
            port_setting.props.priority = val
        elif key == LB.Port.STP_HAIRPIN_MODE:
            port_setting.props.hairpin_mode = val
        elif key == LB.Port.STP_PATH_COST:
            port_setting.props.path_cost = val
        elif key == LB.Port.VLAN_SUBTREE:
            port_setting.clear_vlans()
            for vlan_config in nmstate_port_vlan_to_nm(val):
                port_setting.add_vlan(vlan_config)

    return port_setting


def get_port(nm_device):
    return nm_device.get_slaves()


def get_linux_bridge_config(nm_profile, port_nm_profiles):
    nm_setting = nm_profile.get_setting_bridge()
    if nm_setting:
        info = {
            LB.OPTIONS_SUBTREE: _get_bridge_options(nm_setting),
            LB.PORT_SUBTREE: [
                _get_port_config(port_nm_profile)
                for port_nm_profile in port_nm_profiles
            ],
        }

        return info

    return {}


def _get_bridge_options(nm_setting):
    info = {
        LB.Options.MAC_AGEING_TIME: nm_setting.get_ageing_time(),
        LB.Options.GROUP_FORWARD_MASK: nm_setting.get_group_forward_mask(),
        LB.Options.MULTICAST_SNOOPING: nm_setting.get_multicast_snooping(),
        LB.STP_SUBTREE: _get_stp_options(nm_setting),
    }
    for key, nm_key in NM_BRIDGE_OPTIONS_MAP.items():
        value = getattr(nm_setting.props, nm_key)
        if value is not None:
            if key == LB.Options.GROUP_ADDR:
                value = value.upper()
            info[key] = value
    return info


def _get_stp_options(nm_setting):
    if nm_setting.get_stp():
        return {
            LB.STP.ENABLED: True,
            LB.STP.HELLO_TIME: nm_setting.get_hello_time(),
            LB.STP.MAX_AGE: nm_setting.get_max_age(),
            LB.STP.FORWARD_DELAY: nm_setting.get_forward_delay(),
            LB.STP.PRIORITY: nm_setting.get_priority(),
        }
    else:
        return {LB.STP.ENABLED: False}


def _get_port_config(nm_profile):
    info = {
        LB.Port.NAME: nm_profile.get_interface_name(),
    }
    nm_setting = nm_profile.get_setting_bridge_port()
    if nm_setting:
        info[LB.Port.STP_PRIORITY] = nm_setting.props.priority
        info[LB.Port.STP_HAIRPIN_MODE] = nm_setting.props.hairpin_mode
        info[LB.Port.STP_PATH_COST] = nm_setting.props.path_cost
        if nm_setting.props.vlans:
            info[LB.Port.VLAN_SUBTREE] = get_linux_bridge_port_vlan_config(
                nm_setting
            )

    return info
