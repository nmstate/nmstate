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

from libnmstate.error import NmstateValueError
from libnmstate.schema import OVSBridge as OB

from . import connection
from . import device
from . import nmclient


BRIDGE_TYPE = "ovs-bridge"
INTERNAL_INTERFACE_TYPE = "ovs-interface"
PORT_TYPE = "ovs-port"
PORT_PROFILE_PREFIX = "ovs-port-"
CAPABILITY = "openvswitch"


_BRIDGE_OPTION_NAMES = ["fail-mode", "mcast-snooping-enable", "rstp", "stp"]


def has_ovs_capability():
    try:
        nmclient.NM.DeviceType.OVS_BRIDGE
        return True
    except AttributeError:
        return False


def create_bridge_setting(options):
    bridge_setting = nmclient.NM.SettingOvsBridge.new()
    for option_name, option_value in options.items():
        if option_name == "fail-mode":
            if option_value:
                bridge_setting.props.fail_mode = option_value
        elif option_name == "mcast-snooping-enable":
            bridge_setting.props.mcast_snooping_enable = option_value
        elif option_name == "rstp":
            bridge_setting.props.rstp_enable = option_value
        elif option_name == "stp":
            bridge_setting.props.stp_enable = option_value
        else:
            raise NmstateValueError(
                "Invalid OVS bridge option: '{}'='{}'".format(
                    option_name, option_value
                )
            )

    return bridge_setting


def create_port_setting(options):
    port_setting = nmclient.NM.SettingOvsPort.new()
    for option_name, option_value in options.items():
        if option_name == "tag":
            port_setting.props.tag = option_value
        elif option_name == "vlan-mode":
            port_setting.props.vlan_mode = option_value
        elif option_name == "bond-mode":
            port_setting.props.bond_mode = option_value
        elif option_name == "lacp":
            port_setting.props.lacp = option_value
        elif option_name == "bond-updelay":
            port_setting.props.bond_updelay = option_value
        elif option_name == "bond-downdelay":
            port_setting.props.bond_downdelay = option_value
        else:
            raise NmstateValueError(
                "Invalid OVS port option: '{}'='{}'".format(
                    option_name, option_value
                )
            )

    return port_setting


def create_interface_setting():
    interface_setting = nmclient.NM.SettingOvsInterface.new()
    interface_setting.props.type = "internal"
    return interface_setting


def translate_bridge_options(iface_state):
    br_opts = {}
    bridge_state = iface_state.get("bridge", {}).get("options", {})
    for key in bridge_state.keys() & set(_BRIDGE_OPTION_NAMES):
        br_opts[key] = bridge_state[key]

    return br_opts


def translate_port_options(port_state):
    port_opts = {}

    bond_mode = port_state.get("link-aggregation", {}).get("mode")
    if bond_mode:
        port_opts["bond-mode"] = bond_mode

    return port_opts


def is_ovs_bridge_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.OVS_BRIDGE


def is_ovs_port_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.OVS_PORT


def is_ovs_interface_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.OVS_INTERFACE


def get_bridge_info(bridge_device, devices_info):
    info = get_ovs_info(bridge_device, devices_info)
    if info:
        return {OB.CONFIG_SUBTREE: info}
    else:
        return {}


def get_ovs_info(bridge_device, devices_info):
    port_profiles = _get_slave_profiles(bridge_device, devices_info)
    ports = _get_bridge_ports_info(port_profiles, devices_info)
    options = _get_bridge_options(bridge_device)

    if ports or options:
        return {"port": ports, "options": options}
    else:
        return {}


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
    port_name = port_profile.get_interface_name()
    port_setting = port_profile.get_setting(nmclient.NM.SettingOvsPort)
    ifaces_info = _get_ifaces_info(port_name, devices_info)

    if len(ifaces_info) >= 2:
        # The port has multiple interfaces connected, treat it as a bonding.
        port_info["name"] = port_name
        port_info["link-aggregation"] = {
            "slaves": ifaces_info,
        }
        if port_setting.props.bond_mode:
            port_info["link-aggregation"][
                "mode"
            ] = port_setting.props.bond_mode
    elif len(ifaces_info) == 1:
        # The port has a single interface connected, reflect its information
        # into the port itself.
        iface_info = ifaces_info[0]
        port_info.update(iface_info)

    return port_info


def _get_ifaces_info(port_name, devices_info):
    port_device = device.get_device_by_name(port_name)
    ifaces_info = [
        {"name": profile.get_interface_name()}
        for profile in _get_slave_profiles(port_device, devices_info)
    ]
    return ifaces_info


def _get_bridge_options(bridge_device):
    bridge_options = {}
    con = connection.ConnectionProfile()
    con.import_by_device(bridge_device)
    if con.profile:
        bridge_setting = con.profile.get_setting(nmclient.NM.SettingOvsBridge)
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
