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

from libnmstate.ifaces import ovs
from libnmstate.ifaces.bridge import BridgeIface
from libnmstate.ifaces.ovs import OvsPortIface
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge as OB
from libnmstate.schema import OVSInterface
from libnmstate.schema import OvsDB

from .common import NM


CONTROLLER_TYPE_METADATA = "_controller_type"
CONTROLLER_METADATA = "_controller"
SETTING_OVS_EXTERNALIDS = "SettingOvsExternalIDs"
SETTING_OVS_EXTERNAL_IDS_SETTING_NAME = "ovs-external-ids"

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
        elif option_name == "datapath":
            bridge_setting.props.datapath_type = option_value

    return bridge_setting


def create_ovsdb_external_ids_setting(ovsdb_conf):
    if _is_nm_support_ovs_external_ids():
        nm_setting = getattr(NM, SETTING_OVS_EXTERNALIDS).new()
        for key, value in ovsdb_conf.get(OvsDB.EXTERNAL_IDS, {}).items():
            if not key.startswith("NM."):
                nm_setting.set_data(key, str(value))
        return nm_setting
    else:
        logging.warn(
            "Please upgrade NetworkManger to 1.30+ "
            "for the support OVS external ID modification"
        )
        return None


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
        if down_delay is not None:
            port_setting.props.bond_downdelay = down_delay
        up_delay = lag_state.get(OB.Port.LinkAggregation.Options.UP_DELAY)
        if up_delay is not None:
            port_setting.props.bond_updelay = up_delay

    vlan_state = port_state.get(OB.Port.VLAN_SUBTREE, {})
    if OB.Port.Vlan.MODE in vlan_state:
        if vlan_state[OB.Port.Vlan.MODE] != OB.Port.Vlan.Mode.UNKNOWN:
            port_setting.props.vlan_mode = vlan_state[OB.Port.Vlan.MODE]
    if OB.Port.Vlan.TAG in vlan_state:
        port_setting.props.tag = vlan_state[OB.Port.Vlan.TAG]

    return port_setting


def create_interface_setting(patch_state, dpdk_state):
    interface_setting = NM.SettingOvsInterface.new()
    settings = [interface_setting]

    if patch_state and patch_state.get(OVSInterface.Patch.PEER):
        interface_setting.props.type = "patch"
        settings.append(create_patch_setting(patch_state))
    elif dpdk_state and dpdk_state.get(OVSInterface.Dpdk.DEVARGS):
        interface_setting.props.type = "dpdk"
        settings.append(create_dpdk_setting(dpdk_state))
    else:
        interface_setting.props.type = "internal"

    return settings


def create_patch_setting(patch_state):
    patch_setting = NM.SettingOvsPatch.new()
    patch_setting.props.peer = patch_state[OVSInterface.Patch.PEER]

    return patch_setting


def create_dpdk_setting(dpdk_state):
    dpdk_setting = NM.SettingOvsDpdk.new()
    dpdk_setting.props.devargs = dpdk_state[OVSInterface.Dpdk.DEVARGS]
    dpdk_setting.props.n_rxq = dpdk_state[OVSInterface.Dpdk.RX_QUEUE]

    return dpdk_setting


def get_ovs_bridge_info(nm_dev_ovs_br):
    iface_info = {OB.CONFIG_SUBTREE: {}}
    ports_info = _get_bridge_nmstate_ports_info(nm_dev_ovs_br)
    options = _get_bridge_options(nm_dev_ovs_br)

    if ports_info or options:
        iface_info[OB.CONFIG_SUBTREE] = {
            OB.PORT_SUBTREE: ports_info,
            OB.OPTIONS_SUBTREE: options,
        }
    return iface_info


def get_ovsdb_external_ids(nm_profile):
    iface_info = {}
    if _is_nm_support_ovs_external_ids():
        nm_setting = nm_profile.get_setting_by_name(
            SETTING_OVS_EXTERNAL_IDS_SETTING_NAME
        )
        if nm_setting:
            external_ids = {}
            for key in nm_setting.get_data_keys():
                external_ids[key] = nm_setting.get_data(key)
            iface_info[OvsDB.OVS_DB_SUBTREE] = {
                OvsDB.EXTERNAL_IDS: external_ids
            }
    return iface_info


def _get_bridge_nmstate_ports_info(nm_dev_ovs_br):
    ports_info = []
    for nm_dev_ovs_port in nm_dev_ovs_br.get_slaves():
        port_info = {}
        nm_dev_ovs_ifaces = nm_dev_ovs_port.get_slaves()
        if not nm_dev_ovs_ifaces:
            continue
        if len(nm_dev_ovs_ifaces) == 1:
            port_info[OB.Port.NAME] = nm_dev_ovs_ifaces[0].get_iface()
        else:
            port_info = _get_lag_nmstate_port_info(nm_dev_ovs_port)
        vlan_info = _get_vlan_info(nm_dev_ovs_port)
        if vlan_info:
            port_info[OB.Port.VLAN_SUBTREE] = vlan_info
        ports_info.append(port_info)
    return sorted(ports_info, key=itemgetter(OB.Port.NAME))


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
        dpdk_setting = _get_dpdk_setting(act_con)
        if dpdk_setting:
            info[OVSInterface.DPDK_CONFIG_SUBTREE] = {
                OVSInterface.Dpdk.DEVARGS: dpdk_setting.props.devargs,
                OVSInterface.Dpdk.RX_QUEUE: dpdk_setting.props.n_rxq,
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


def _get_dpdk_setting(act_con):
    """
    Get NM.SettingOvsDpdk from NM.ActiveConnection.
    For any error, return None.
    """
    remote_con = act_con.get_connection()
    if remote_con:
        return remote_con.get_setting_by_name(NM.SETTING_OVS_DPDK_SETTING_NAME)

    return None


def _get_lag_nmstate_port_info(nm_dev_ovs_port):
    OVS_LAG = OB.Port.LinkAggregation

    lag = {
        OVS_LAG.PORT_SUBTREE: sorted(
            [
                {OVS_LAG.Port.NAME: nm_dev_ovs_iface.get_iface()}
                for nm_dev_ovs_iface in nm_dev_ovs_port.get_slaves()
            ],
            key=itemgetter(OVS_LAG.Port.NAME),
        ),
    }
    mode = _get_lag_mode(nm_dev_ovs_port)
    if mode:
        lag[OVS_LAG.MODE] = mode
    up_delay, down_delay = _get_lag_options(nm_dev_ovs_port)
    if up_delay is not None:
        lag[OVS_LAG.Options.UP_DELAY] = up_delay
    if down_delay is not None:
        lag[OVS_LAG.Options.DOWN_DELAY] = down_delay
    return {
        OB.Port.NAME: nm_dev_ovs_port.get_iface(),
        OB.Port.LINK_AGGREGATION_SUBTREE: lag,
    }


def _get_lag_options(nm_dev_ovs_port):
    """
    Use applied profile to get ovs bond options
    """
    up_delay = None
    down_delay = None
    nm_setting = _get_nm_setting_ovs_port(nm_dev_ovs_port)
    if nm_setting:
        up_delay = nm_setting.props.bond_updelay
        down_delay = nm_setting.props.bond_downdelay

    return up_delay, down_delay


def _get_lag_mode(nm_dev_ovs_port):
    """
    TODO: Use applied profile instead of on-disk one.
    """
    mode = None
    nm_setting = _get_nm_setting_ovs_port(nm_dev_ovs_port)
    if nm_setting:
        lacp = nm_setting.props.lacp
        mode = nm_setting.props.bond_mode
        if not mode:
            if lacp == LacpValue.ACTIVE:
                mode = OB.Port.LinkAggregation.Mode.LACP
            else:
                mode = OB.Port.LinkAggregation.Mode.ACTIVE_BACKUP
    return mode


def _get_vlan_info(nm_dev_ovs_port):
    nm_setting = _get_nm_setting_ovs_port(nm_dev_ovs_port)
    if nm_setting:
        vlan_mode = nm_setting.props.vlan_mode
        if vlan_mode:
            nmstate_vlan_mode = NM_OVS_VLAN_MODE_MAP.get(
                vlan_mode, OB.Port.Vlan.Mode.UNKNOWN
            )
            if nmstate_vlan_mode == OB.Port.Vlan.Mode.UNKNOWN:
                logging.warning(
                    f"OVS Port VLAN mode '{vlan_mode}' is not supported yet"
                )
                return {OB.Port.Vlan.MODE: OB.Port.Vlan.Mode.UNKNOWN}
            else:
                return {
                    OB.Port.Vlan.MODE: nmstate_vlan_mode,
                    OB.Port.Vlan.TAG: nm_setting.get_tag(),
                }
    return {}


def _get_nm_setting_ovs_port(nm_dev_ovs_port):
    nm_ac = nm_dev_ovs_port.get_active_connection()
    if nm_ac:
        nm_profile = nm_ac.props.connection
        if nm_profile:
            return nm_profile.get_setting(NM.SettingOvsPort)
    return None


def _get_bridge_options(bridge_device):
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
        bridge_options["datapath"] = bridge_setting.props.datapath_type

    return bridge_options


def create_iface_for_nm_ovs_port(iface):
    iface_name = iface.name
    iface_info = iface.to_dict()
    port_options = iface_info.get(BridgeIface.BRPORT_OPTIONS_METADATA)
    if ovs.is_ovs_lag_port(port_options):
        port_name = port_options[OB.Port.NAME]
    else:
        port_name = iface_name
    return OvsPortIface(
        {
            Interface.NAME: port_name,
            Interface.TYPE: InterfaceType.OVS_PORT,
            Interface.STATE: iface.state,
            OB.OPTIONS_SUBTREE: port_options,
            CONTROLLER_METADATA: iface_info[CONTROLLER_METADATA],
            CONTROLLER_TYPE_METADATA: iface_info[CONTROLLER_TYPE_METADATA],
        }
    )


def _is_nm_support_ovs_external_ids():
    return hasattr(NM, SETTING_OVS_EXTERNALIDS)
