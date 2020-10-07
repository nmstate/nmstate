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
from operator import itemgetter

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge as OB
from libnmstate.schema import OVSInterface
from libnmstate.ifaces import ovs
from libnmstate.ifaces.bridge import BridgeIface

from . import connection
from .common import NM


PORT_PROFILE_PREFIX = "ovs-port-"

CONTROLLER_TYPE_METADATA = "_controller_type"
CONTROLLER_METADATA = "_controller"

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


def create_interface_setting(patch_state):
    interface_setting = NM.SettingOvsInterface.new()
    settings = [interface_setting]

    if patch_state and patch_state.get(OVSInterface.Patch.PEER):
        interface_setting.props.type = "patch"
        settings.append(create_patch_setting(patch_state))
    else:
        interface_setting.props.type = "internal"

    return settings


def create_patch_setting(patch_state):
    patch_setting = NM.SettingOvsPatch.new()
    patch_setting.props.peer = patch_state[OVSInterface.Patch.PEER]

    return patch_setting


def is_ovs_bridge_type_id(type_id):
    return type_id == NM.DeviceType.OVS_BRIDGE


def is_ovs_port_type_id(type_id):
    return type_id == NM.DeviceType.OVS_PORT


def is_ovs_interface_type_id(type_id):
    return type_id == NM.DeviceType.OVS_INTERFACE


def get_port_by_port(nmdev):
    active_con = connection.get_device_active_connection(nmdev)
    if active_con:
        controller = active_con.get_controller()
        if controller and is_ovs_port_type_id(controller.get_device_type()):
            return controller
    return None


def get_ovs_info(context, bridge_device, devices_info):
    port_profiles = _get_port_profiles(bridge_device, devices_info)
    ports = _get_bridge_ports_info(context, port_profiles, devices_info)
    options = _get_bridge_options(context, bridge_device)

    if ports or options:
        return {"port": ports, "options": options}
    else:
        return {}


def get_interface_info(act_con):
    """
    Get OVS interface information from the NM profile.
    """
    info = {}
    if act_con:
        patch_setting = _get_patch_setting(act_con)
        if patch_setting:
            info[OVSInterface.PATCH_CONFIG_SUBTREE] = {
                OVSInterface.Patch.PEER: patch_setting.props.peer,
            }

    return info


def _get_patch_setting(act_con):
    """
    Get NM.SettingOvsPatch from NM.ActiveConnection.
    For any error, return None.
    """
    remote_con = act_con.get_connection()
    if remote_con:
        return remote_con.get_setting_ovs_patch()

    return None


def get_port(nm_device):
    return nm_device.get_slaves()


def _get_bridge_ports_info(context, port_profiles, devices_info):
    ports_info = []
    for p in port_profiles:
        port_info = _get_bridge_port_info(context, p, devices_info)
        if port_info:
            ports_info.append(port_info)
    ports_info.sort(key=itemgetter(OB.Port.NAME))
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
    port_port_profiles = _get_port_profiles(port_device, devices_info)
    port_port_names = [c.get_interface_name() for c in port_port_profiles]

    if port_port_names:
        number_of_interfaces = len(port_port_names)
        if number_of_interfaces == 1:
            port_info[OB.Port.NAME] = port_port_names[0]
        else:
            port_lag_info = _get_lag_info(
                port_name, port_setting, port_port_names
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


def _get_lag_info(port_name, port_setting, port_names):
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
        OB.Port.LinkAggregation.PORT_SUBTREE: sorted(
            [
                {OB.Port.LinkAggregation.Port.NAME: iface_name}
                for iface_name in port_names
            ],
            key=itemgetter(OB.Port.LinkAggregation.Port.NAME),
        ),
    }
    return port_info


def _get_bridge_options(context, bridge_device):
    bridge_options = {}
    bridge_profile = None
    act_conn = bridge_device.get_active_connection()
    if act_conn:
        bridge_profile = act_conn.props.connection

    if bridge_profile:
        bridge_setting = bridge_profile.get_setting(NM.SettingOvsBridge)
        bridge_options["stp"] = bridge_setting.props.stp_enable
        bridge_options["rstp"] = bridge_setting.props.rstp_enable
        bridge_options["fail-mode"] = bridge_setting.props.fail_mode or ""
        bridge_options[
            "mcast-snooping-enable"
        ] = bridge_setting.props.mcast_snooping_enable

    return bridge_options


def _get_port_profiles(controller_device, devices_info):
    port_profiles = []
    for dev, _ in devices_info:
        active_con = connection.get_device_active_connection(dev)
        if active_con:
            controller = active_con.props.master
            if controller and (
                controller.get_iface() == controller_device.get_iface()
            ):
                profile = active_con.props.connection
                if profile:
                    port_profiles.append(profile)
    return port_profiles


def create_ovs_proxy_iface_info(iface):
    """
        Prepare the state of the "proxy" interface. These are interfaces that
        exist as NM entities/profiles, but are invisible to the API.
        These proxy interfaces state is created as a side effect of other
        ifaces definition.
        In OVS case, the port profile is the proxy, it is not part of the
        public state of the system, but internal to the NM provider.
        """
    iface_info = iface.to_dict()
    controller_type = iface_info.get(CONTROLLER_TYPE_METADATA)
    if controller_type != InterfaceType.OVS_BRIDGE:
        return None
    port_opts_metadata = iface_info.get(BridgeIface.BRPORT_OPTIONS_METADATA)
    if port_opts_metadata is None:
        return None
    port_iface_desired_state = _create_ovs_port_iface_desired_state(
        port_opts_metadata, iface, iface_info
    )
    # The "visible" port/interface needs to point to the port profile
    iface.set_controller(
        port_iface_desired_state[Interface.NAME], InterfaceType.OVS_PORT
    )

    return port_iface_desired_state


def _create_ovs_port_iface_desired_state(port_options, iface, iface_info):
    iface_name = iface.name
    if ovs.is_ovs_lag_port(port_options):
        port_name = port_options[OB.Port.NAME]
    else:
        port_name = PORT_PROFILE_PREFIX + iface_name
    return {
        Interface.NAME: port_name,
        Interface.TYPE: InterfaceType.OVS_PORT,
        Interface.STATE: iface_info[Interface.STATE],
        OB.OPTIONS_SUBTREE: port_options,
        CONTROLLER_METADATA: iface_info[CONTROLLER_METADATA],
        CONTROLLER_TYPE_METADATA: iface_info[CONTROLLER_TYPE_METADATA],
    }
