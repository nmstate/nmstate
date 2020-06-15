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

import glob
import os

from libnmstate.nm import connection
from libnmstate.nm.bridge_port_vlan import PortVlanFilter
from libnmstate.schema import LinuxBridge as LB
from .common import NM
from .common import nm_version_bigger_or_equal_to


BRIDGE_TYPE = "bridge"

BRIDGE_PORT_NMSTATE_TO_SYSFS = {
    LB.Port.STP_HAIRPIN_MODE: "hairpin_mode",
    LB.Port.STP_PATH_COST: "path_cost",
    LB.Port.STP_PRIORITY: "priority",
}

SYSFS_USER_HZ_KEYS = [
    "forward_delay",
    "ageing_time",
    "hello_time",
    "max_age",
]

OPT = LB.Options

EXTRA_OPTIONS_MAP = {
    OPT.HELLO_TIMER: "hello_timer",
    OPT.GC_TIMER: "gc_timer",
    OPT.MULTICAST_ROUTER: "multicast_router",
    OPT.GROUP_ADDR: "group_addr",
    OPT.HASH_MAX: "hash_max",
    OPT.MULTICAST_LAST_MEMBER_COUNT: "multicast_last_member_count",
    OPT.MULTICAST_LAST_MEMBER_INTERVAL: "multicast_last_member_interval",
    OPT.MULTICAST_QUERIER: "multicast_querier",
    OPT.MULTICAST_QUERIER_INTERVAL: "multicast_querier_interval",
    OPT.MULTICAST_QUERY_USE_IFADDR: "multicast_query_use_ifaddr",
    OPT.MULTICAST_QUERY_INTERVAL: "multicast_query_interval",
    OPT.MULTICAST_QUERY_RESPONSE_INTERVAL: "multicast_query_response_interval",
    OPT.MULTICAST_STARTUP_QUERY_COUNT: "multicast_startup_query_count",
    OPT.MULTICAST_STARTUP_QUERY_INTERVAL: "multicast_startup_query_interval",
}

BOOL_OPTIONS = (OPT.MULTICAST_QUERIER, OPT.MULTICAST_QUERY_USE_IFADDR)

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
        elif (
            nm_version_bigger_or_equal_to("1.25.2")
            and key in NM_BRIDGE_OPTIONS_MAP
        ):
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
            for vlan_config in _create_port_vlans_setting(val):
                port_setting.add_vlan(vlan_config)

    return port_setting


def _create_port_vlans_setting(val):
    trunk_tags = val.get(LB.Port.Vlan.TRUNK_TAGS)
    tag = val.get(LB.Port.Vlan.TAG)
    enable_native_vlan = val.get(LB.Port.Vlan.ENABLE_NATIVE)
    port_vlan_config = PortVlanFilter()
    port_vlan_config.create_configuration(trunk_tags, tag, enable_native_vlan)
    return (vlan_config for vlan_config in port_vlan_config.to_nm())


def get_info(context, nmdev):
    """
    Provides the current active values for a device
    """
    info = {}
    if nmdev.get_device_type() != NM.DeviceType.BRIDGE:
        return info
    bridge_setting = _get_bridge_setting(context, nmdev)
    if not bridge_setting:
        return info

    port_profiles_by_name = _get_slave_profiles_by_name(nmdev)
    port_names_sysfs = _get_slaves_names_from_sysfs(nmdev.get_iface())
    props = _get_sysfs_bridge_options(nmdev.get_iface())
    info[LB.CONFIG_SUBTREE] = {
        LB.PORT_SUBTREE: _get_bridge_ports_info(
            port_profiles_by_name,
            port_names_sysfs,
            vlan_filtering_enabled=bridge_setting.get_vlan_filtering(),
        ),
        LB.OPTIONS_SUBTREE: {
            LB.Options.MAC_AGEING_TIME: props["ageing_time"],
            LB.Options.GROUP_FORWARD_MASK: props["group_fwd_mask"],
            LB.Options.MULTICAST_SNOOPING: props["multicast_snooping"] > 0,
            LB.STP_SUBTREE: {
                LB.STP.ENABLED: props["stp_state"] > 0,
                LB.STP.PRIORITY: props["priority"],
                LB.STP.FORWARD_DELAY: props["forward_delay"],
                LB.STP.HELLO_TIME: props["hello_time"],
                LB.STP.MAX_AGE: props["max_age"],
            },
        },
    }

    if nm_version_bigger_or_equal_to("1.25.2"):
        for schema_name, sysfs_key_name in EXTRA_OPTIONS_MAP.items():
            value = props[sysfs_key_name]
            if schema_name == LB.Options.GROUP_ADDR:
                value = value.upper()
            elif schema_name in BOOL_OPTIONS:
                value = value > 0
            info[LB.CONFIG_SUBTREE][LB.OPTIONS_SUBTREE][schema_name] = value
    return info


def get_slaves(nm_device):
    return nm_device.get_slaves()


def _get_bridge_setting(context, nmdev):
    bridge_setting = None
    bridge_con_profile = connection.ConnectionProfile(context)
    bridge_con_profile.import_by_device(nmdev)
    if bridge_con_profile.profile:
        bridge_setting = bridge_con_profile.profile.get_setting_bridge()
    return bridge_setting


def _get_bridge_ports_info(
    port_profiles_by_name, port_names_sysfs, vlan_filtering_enabled=False
):
    ports_info_by_name = {
        name: _get_bridge_port_info(name) for name in port_names_sysfs
    }

    for name, p in port_profiles_by_name.items():
        port_info = ports_info_by_name.get(name, {})
        if port_info:
            if vlan_filtering_enabled:
                bridge_vlan_config = p.get_setting_bridge_port().props.vlans
                port_vlan = PortVlanFilter()
                port_vlan.import_from_bridge_settings(bridge_vlan_config)
                port_info[LB.Port.VLAN_SUBTREE] = port_vlan.to_dict()
    return list(ports_info_by_name.values())


def _get_slave_profiles_by_name(master_device):
    slaves_profiles_by_name = {}
    for dev in master_device.get_slaves():
        active_con = connection.get_device_active_connection(dev)
        if active_con:
            slaves_profiles_by_name[
                dev.get_iface()
            ] = active_con.props.connection
    return slaves_profiles_by_name


def _get_bridge_port_info(port_name):
    """Report port runtime information from sysfs."""
    port = {LB.Port.NAME: port_name}
    for option, option_sysfs in BRIDGE_PORT_NMSTATE_TO_SYSFS.items():
        sysfs_path = f"/sys/class/net/{port_name}/brport/{option_sysfs}"
        with open(sysfs_path) as f:
            option_value = int(f.read())
            if option == LB.Port.STP_HAIRPIN_MODE:
                option_value = bool(option_value)
        port[option] = option_value
    return port


def _get_slaves_names_from_sysfs(master):
    """
    We need to use glob in order to get the slaves name due to bug in
    NetworkManager.
    Ref: https://bugzilla.redhat.com/show_bug.cgi?id=1809547
    """
    slaves = []
    for sysfs_slave in glob.iglob(f"/sys/class/net/{master}/lower_*"):
        # The format is lower_<iface>, we need to remove the "lower_" prefix
        prefix_length = len("lower_")
        slaves.append(os.path.basename(sysfs_slave)[prefix_length:])
    return slaves


def _get_sysfs_bridge_options(iface_name):
    user_hz = os.sysconf("SC_CLK_TCK")
    options = {}
    for sysfs_file_path in glob.iglob(f"/sys/class/net/{iface_name}/bridge/*"):
        key = os.path.basename(sysfs_file_path)
        try:
            with open(sysfs_file_path) as fd:
                value = fd.read().rstrip("\n")
                options[key] = value
                options[key] = int(value, base=0)
        except Exception:
            pass
    for key, value in options.items():
        if key in SYSFS_USER_HZ_KEYS:
            options[key] = int(value / user_hz)
    return options
