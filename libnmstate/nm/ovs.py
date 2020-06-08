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
import logging

from libnmstate.schema import OVSBridge as OB

from . import connection
from .common import NM


PORT_PROFILE_PREFIX = "ovs-port-"

NM_OVS_VLAN_MODE_MAP = {
    "trunk": OB.Port.Vlan.Mode.TRUNK,
    "access": OB.Port.Vlan.Mode.ACCESS,
    "native-tagged": OB.Port.Vlan.Mode.TRUNK,
    "native-untagged": OB.Port.Vlan.Mode.UNKNOWN,  # Not supported yet
    "dot1q-tunnel": OB.Port.Vlan.Mode.UNKNOWN,  # Not supported yet
}


class LacpValue:
    ACTIVE = "active"
    OFF = "off"


def has_ovs_capability(nm_client):
    return NM.Capability.OVS in nm_client.get_capabilities()


def create_bridge_setting(options_state):
    bridge_setting = NM.SettingOvsBridge.new()
    for option_name, option_value in options_state.items():
        if option_name == "fail-mode":
            if option_value:
                bridge_setting.props.fail_mode = option_value
        elif option_name == "mcast-snooping-enable":
            bridge_setting.props.mcast_snooping_enable = option_value
        elif option_name == "rstp":
            bridge_setting.props.rstp_enable = option_value
        elif option_name == "stp":
            bridge_setting.props.stp_enable = option_value

    return bridge_setting


def create_port_setting(port_state):
    port_setting = NM.SettingOvsPort.new()

    lag_state = port_state.get(OB.Port.LINK_AGGREGATION_SUBTREE)
    if lag_state:
        mode = lag_state.get(OB.Port.LinkAggregation.MODE)
        if mode == OB.Port.LinkAggregation.Mode.LACP:
            port_setting.props.lacp = LacpValue.ACTIVE
        elif mode in (
            OB.Port.LinkAggregation.Mode.ACTIVE_BACKUP,
            OB.Port.LinkAggregation.Mode.BALANCE_SLB,
        ):
            port_setting.props.lacp = LacpValue.OFF
            port_setting.props.bond_mode = mode
        elif mode == OB.Port.LinkAggregation.Mode.BALANCE_TCP:
            port_setting.props.lacp = LacpValue.ACTIVE
            port_setting.props.bond_mode = mode

        down_delay = lag_state.get(OB.Port.LinkAggregation.Options.DOWN_DELAY)
        if down_delay:
            port_setting.props.bond_downdelay = down_delay
        up_delay = lag_state.get(OB.Port.LinkAggregation.Options.UP_DELAY)
        if up_delay:
            port_setting.props.bond_updelay = up_delay

    vlan_state = port_state.get(OB.Port.VLAN_SUBTREE, {})
    if OB.Port.Vlan.MODE in vlan_state:
        if vlan_state[OB.Port.Vlan.MODE] != OB.Port.Vlan.Mode.UNKNOWN:
            port_setting.props.vlan_mode = vlan_state[OB.Port.Vlan.MODE]
    if OB.Port.Vlan.TAG in vlan_state:
        port_setting.props.tag = vlan_state[OB.Port.Vlan.TAG]

    return port_setting


def create_interface_setting():
    interface_setting = NM.SettingOvsInterface.new()
    interface_setting.props.type = "internal"
    return interface_setting


def is_ovs_bridge_type_id(type_id):
    return type_id == NM.DeviceType.OVS_BRIDGE


def is_ovs_port_type_id(type_id):
    return type_id == NM.DeviceType.OVS_PORT


def is_ovs_interface_type_id(type_id):
    return type_id == NM.DeviceType.OVS_INTERFACE


def get_port_by_slave(nmdev):
    active_con = connection.get_device_active_connection(nmdev)
    if active_con:
        master = active_con.get_master()
        if master and is_ovs_port_type_id(master.get_device_type()):
            return master
    return None


def get_ovs_info(context, bridge_device, devices_info):
    port_profiles = _get_slave_profiles(bridge_device, devices_info)
    ports = _get_bridge_ports_info(context, port_profiles, devices_info)
    options = _get_bridge_options(context, bridge_device)

    if ports or options:
        return {"port": ports, "options": options}
    else:
        return {}


def get_slaves(nm_device):
    return nm_device.get_slaves()


def _get_bridge_ports_info(context, port_profiles, devices_info):
    ports_info = []
    for p in port_profiles:
        port_info = _get_bridge_port_info(context, p, devices_info)
        if port_info:
            ports_info.append(port_info)
    return ports_info


def _get_bridge_port_info(context, port_profile, devices_info):
    """
    Report port information.
    Note: The current implementation supports only system OVS ports and
    access vlan-mode (trunks are not supported).
    """
    port_info = {}

    port_setting = port_profile.get_setting(NM.SettingOvsPort)
    vlan_mode = port_setting.props.vlan_mode

    port_name = port_profile.get_interface_name()
    port_device = context.get_nm_dev(port_name)
    port_slave_profiles = _get_slave_profiles(port_device, devices_info)
    port_slave_names = [c.get_interface_name() for c in port_slave_profiles]

    if port_slave_names:
        number_of_interfaces = len(port_slave_names)
        if number_of_interfaces == 1:
            port_info[OB.Port.NAME] = port_slave_names[0]
        else:
            port_lag_info = _get_lag_info(
                port_name, port_setting, port_slave_names
            )
            port_info.update(port_lag_info)

        if vlan_mode:
            nmstate_vlan_mode = NM_OVS_VLAN_MODE_MAP.get(
                vlan_mode, OB.Port.Vlan.Mode.UNKNOWN
            )
            if nmstate_vlan_mode == OB.Port.Vlan.Mode.UNKNOWN:
                logging.warning(
                    f"OVS Port VLAN mode '{vlan_mode}' is not supported yet"
                )
            port_info[OB.Port.VLAN_SUBTREE] = {
                OB.Port.Vlan.MODE: nmstate_vlan_mode,
                OB.Port.Vlan.TAG: port_setting.get_tag(),
            }
    return port_info


def _get_lag_info(port_name, port_setting, port_slave_names):
    port_info = {}

    lacp = port_setting.props.lacp
    mode = port_setting.props.bond_mode
    if not mode:
        if lacp == LacpValue.ACTIVE:
            mode = OB.Port.LinkAggregation.Mode.LACP
        else:
            mode = OB.Port.LinkAggregation.Mode.ACTIVE_BACKUP
    port_info[OB.Port.NAME] = port_name
    port_info[OB.Port.LINK_AGGREGATION_SUBTREE] = {
        OB.Port.LinkAggregation.MODE: mode,
        OB.Port.LinkAggregation.SLAVES_SUBTREE: [
            {OB.Port.LinkAggregation.Slave.NAME: iface_name}
            for iface_name in port_slave_names
        ],
    }
    return port_info


def _get_bridge_options(context, bridge_device):
    bridge_options = {}
    con = connection.ConnectionProfile(context)
    con.import_by_device(bridge_device)
    if con.profile:
        bridge_setting = con.profile.get_setting(NM.SettingOvsBridge)
        bridge_options["stp"] = bridge_setting.props.stp_enable
        bridge_options["rstp"] = bridge_setting.props.rstp_enable
        bridge_options["fail-mode"] = bridge_setting.props.fail_mode or ""
        bridge_options[
            "mcast-snooping-enable"
        ] = bridge_setting.props.mcast_snooping_enable

    return bridge_options


def _get_slave_profiles(master_device, devices_info):
    slave_profiles = []
    for dev, _ in devices_info:
        active_con = connection.get_device_active_connection(dev)
        if active_con:
            master = active_con.props.master
            if master and (master.get_iface() == master_device.get_iface()):
                slave_profiles.append(active_con.props.connection)
    return slave_profiles
