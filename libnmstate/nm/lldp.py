#
# Copyright (c) 2020 Red Hat, Inc.
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

from libnmstate.schema import LLDP

from .common import NM


NM_VLAN_ID_KEY = "vid"
NM_VLAN_NAME_KEY = "name"
NM_MACPHY_AUTONEG_KEY = "autoneg"
NM_MACPHY_PMD_AUTONEG_KEY = "pmd-autoneg-cap"
NM_MACPHY_MAU_TYPE_KEY = "operational-mau-type"
NM_PPVLAN_ID_KEY = "ppvid"
NM_PPVLAN_FLAGS_KEY = "flags"
NM_MANAGEMENT_ADDR_KEY = "address"
NM_MANAGEMENT_ADDR_TYPE_KEY = "address-subtype"
NM_MANAGEMENT_ADDR_IFACE_NUMBER_KEY = "interface-number"
NM_MANAGEMENT_ADDR_IFACE_NUMBER_TYPE_KEY = "interface-number-subtype"
NM_MANAGEMENT_ADDR_TYPE_IPV4 = 1
NM_MANAGEMENT_ADDR_TYPE_MAC = 6
NM_INTERFACE_TYPE_IFINDEX = 2
NM_INTERFACE_TYPE_SYSTEM_PORT = 3
NM_LLDP_STATUS_DEFAULT = -1
CHASSIS_TYPE_UNKNOWN = "unknown"
PORT_TYPE_UNKNOWN = "unknown"

CHASSIS_ID_TLV = 1
PORT_TLV = 2
SYSTEM_NAME_TLV = 5
SYSTEM_DESCRIPTION_TLV = 6
SYSTEM_CAPABILITIES_TLV = 7
MANAGEMENT_ADDRESSES_TLV = 8
ORGANIZATION_SPECIFIC_TLV = 127

IEEE = "00:80:c2"
PORT_VLAN_SUBTYPE_TLV = 2
VLAN_SUBTYPE_TLV = 3

IEEE_802_3 = "00:12:0f"
MAC_PHY_SUBTYPE_TLV = 1
MFS_SUBTYPE_TLV = 4

LLDP_CAP_NAMES = {
    0b1: "Other",
    0b10: "Repeater",
    0b100: "MAC Bridge component",
    0b1000: "802.11 Access Point (AP)",
    0b1_0000: "Router",
    0b10_0000: "Telephone",
    0b100_0000: "DOCSIS cable device",
    0b1000_0000: "Station Only",
    0b1_0000_0000: "C-VLAN component",
    0b10_0000_0000: "S-VLAN component",
    0b100_0000_0000: "Two-port MAC Relay component",
}


LLDP_CHASSIS_TYPE_TO_NMSTATE = [
    "Reserved",
    "Chassis component",
    "Interface alias",
    "Port component",
    "MAC address",
    "Network address",
    "Interface name",
    "Locally assigned",
]


LLDP_PORT_TYPE_TO_NMSTATE = [
    "Reserved",
    "Interface alias",
    "Port component",
    "MAC address",
    "Network address",
    "Interface name",
    "Agent circuit ID",
    "Locally assigned",
]


def apply_lldp_setting(con_setting, iface_desired_state):
    lldp_status = iface_desired_state.get(LLDP.CONFIG_SUBTREE, {}).get(
        LLDP.ENABLED, None
    )
    if lldp_status is not None:
        lldp_status = int(lldp_status)
        con_setting.setting.props.lldp = lldp_status


def get_info(nm_client, nmdev):
    """
    Provides the current LLDP neighbors information
    """
    lldp_status = _get_lldp_status(nm_client, nmdev)
    info = {}
    if lldp_status == NM_LLDP_STATUS_DEFAULT or not lldp_status:
        info[LLDP.ENABLED] = False
    else:
        info[LLDP.ENABLED] = True
        _get_neighbors_info(info, nmdev)

    return {LLDP.CONFIG_SUBTREE: info}


def _get_lldp_status(nm_client, nmdev):
    """
    Default means NM global config file value which is by default disabled.
    According to NM folks, there is no way from libnm to know if lldp is
    enable or not with libnm if the value in the profile is default.
    Therefore, the best option is to force the users to enable it explicitly.
    This is going to be solved by a property in the NM.Device object to know if
    the device is listening on LLDP.

    Ref: https://bugzilla.redhat.com/1832273
    """
    lldp_status = None
    lldp_profile = None
    act_conn = nmdev.get_active_connection()
    if act_conn:
        lldp_profile = act_conn.props.connection
    if lldp_profile:
        con_setting = lldp_profile.get_setting_connection()
        if con_setting:
            lldp_status = con_setting.get_lldp()

    return lldp_status


def _get_neighbors_info(info, nmdev):
    neighbors = nmdev.get_lldp_neighbors()
    info_neighbors = []
    for neighbor in neighbors:
        n_info = []
        _add_neighbor_system_info(neighbor, n_info)
        _add_neighbor_chassis_info(neighbor, n_info)
        _add_neighbor_port_info(neighbor, n_info)
        _add_neighbor_vlans_info(neighbor, n_info)
        _add_neighbor_macphy_info(neighbor, n_info)
        _add_neighbor_port_vlans_info(neighbor, n_info)
        _add_neighbor_management_addresses(neighbor, n_info)
        _add_max_frame_size(neighbor, n_info)
        info_neighbors.append(n_info)

    if info_neighbors:
        info[LLDP.NEIGHBORS_SUBTREE] = info_neighbors


def _add_neighbor_system_info(neighbor, info):
    sys_name = neighbor.get_attr_value(NM.LLDP_ATTR_SYSTEM_NAME)
    if sys_name:
        sys_name_object = {
            LLDP.Neighbors.TLV_TYPE: SYSTEM_NAME_TLV,
            NM.LLDP_ATTR_SYSTEM_NAME: sys_name.get_string(),
        }
        info.append(sys_name_object)

    sys_desc = neighbor.get_attr_value(NM.LLDP_ATTR_SYSTEM_DESCRIPTION)
    if sys_desc:
        sys_desc_object = {
            LLDP.Neighbors.TLV_TYPE: SYSTEM_DESCRIPTION_TLV,
            NM.LLDP_ATTR_SYSTEM_DESCRIPTION: sys_desc.get_string().rstrip(),
        }
        info.append(sys_desc_object)

    sys_caps = neighbor.get_attr_value(NM.LLDP_ATTR_SYSTEM_CAPABILITIES)
    if sys_caps:
        sys_caps_object = {
            LLDP.Neighbors.TLV_TYPE: SYSTEM_CAPABILITIES_TLV,
            NM.LLDP_ATTR_SYSTEM_CAPABILITIES: _decode_sys_caps(
                sys_caps.get_uint32()
            ),
        }
        info.append(sys_caps_object)


def _decode_sys_caps(code):
    capabilities = []
    for mask, capability in LLDP_CAP_NAMES.items():
        if code & mask:
            capabilities.append(capability)
    return capabilities


def _add_neighbor_chassis_info(neighbor, info):
    chassis_info = {}
    chassis_object = {}
    chassis_id = neighbor.get_attr_value(NM.LLDP_ATTR_CHASSIS_ID)
    if chassis_id:
        chassis_object[NM.LLDP_ATTR_CHASSIS_ID] = chassis_id.get_string()

    chassis_id_type = neighbor.get_attr_value(NM.LLDP_ATTR_CHASSIS_ID_TYPE)
    if chassis_id_type:
        chassis_object[
            NM.LLDP_ATTR_CHASSIS_ID_TYPE
        ] = chassis_id_type.get_uint32()
        chassis_object[LLDP.Neighbors.DESCRIPTION] = _decode_chassis_type(
            chassis_id_type.get_uint32()
        )

    if chassis_object:
        chassis_info[LLDP.Neighbors.TLV_TYPE] = CHASSIS_ID_TLV
        chassis_info.update(chassis_object)
        info.append(chassis_info)


def _decode_chassis_type(code):
    try:
        return LLDP_CHASSIS_TYPE_TO_NMSTATE[code]
    except IndexError:
        return CHASSIS_TYPE_UNKNOWN


def _add_neighbor_port_info(neighbor, info):
    port_info = {}
    port_object = {}
    port_id = neighbor.get_attr_value(NM.LLDP_ATTR_PORT_ID)
    if port_id:
        port_object[NM.LLDP_ATTR_PORT_ID] = port_id.get_string()

    port_type = neighbor.get_attr_value(NM.LLDP_ATTR_PORT_ID_TYPE)
    if port_type:
        port_object[NM.LLDP_ATTR_PORT_ID_TYPE] = port_type.get_uint32()
        port_object[LLDP.Neighbors.DESCRIPTION] = _decode_port_type(
            port_type.get_uint32()
        )

    if port_object:
        port_info[LLDP.Neighbors.TLV_TYPE] = PORT_TLV
        port_info.update(port_object)
        info.append(port_info)


def _decode_port_type(code):
    try:
        return LLDP_PORT_TYPE_TO_NMSTATE[code]
    except IndexError:
        return PORT_TYPE_UNKNOWN


def _add_neighbor_vlans_info(neighbor, info):
    vlans_info = {}
    vlan_objects = []
    vlans = neighbor.get_attr_value(NM.LLDP_ATTR_IEEE_802_1_VLANS)
    if vlans:
        vlans = vlans.unpack()
        for vlan in vlans:
            vlan_object = vlan.copy()
            vlan_object[NM_VLAN_NAME_KEY] = vlan_object[
                NM_VLAN_NAME_KEY
            ].replace("\\000", "")
            if vlan_object:
                vlan_objects.append(vlan_object)

    if vlan_objects:
        vlans_info[LLDP.Neighbors.TLV_TYPE] = ORGANIZATION_SPECIFIC_TLV
        vlans_info[LLDP.Neighbors.ORGANIZATION_CODE] = IEEE
        vlans_info[LLDP.Neighbors.TLV_SUBTYPE] = VLAN_SUBTYPE_TLV
        vlans_info[NM.LLDP_ATTR_IEEE_802_1_VLANS] = vlan_objects
        info.append(vlans_info)


def _add_neighbor_macphy_info(neighbor, info):
    macphy_info = {}
    macphy_object = {}
    macphy_conf = neighbor.get_attr_value(NM.LLDP_ATTR_IEEE_802_3_MAC_PHY_CONF)
    if macphy_conf:
        macphy_object[NM_MACPHY_AUTONEG_KEY] = bool(
            macphy_conf[NM_MACPHY_AUTONEG_KEY]
        )
        macphy_object[NM_MACPHY_PMD_AUTONEG_KEY] = macphy_conf[
            NM_MACPHY_PMD_AUTONEG_KEY
        ]
        macphy_object[NM_MACPHY_MAU_TYPE_KEY] = macphy_conf[
            NM_MACPHY_MAU_TYPE_KEY
        ]

        macphy_info[LLDP.Neighbors.TLV_TYPE] = ORGANIZATION_SPECIFIC_TLV
        macphy_info[LLDP.Neighbors.ORGANIZATION_CODE] = IEEE_802_3
        macphy_info[LLDP.Neighbors.TLV_SUBTYPE] = MAC_PHY_SUBTYPE_TLV
        macphy_info[NM.LLDP_ATTR_IEEE_802_3_MAC_PHY_CONF] = macphy_object
        info.append(macphy_info)


def _add_neighbor_port_vlans_info(neighbor, info):
    port_vlan_objects = []
    port_vlans_info = {}
    port_vlans = neighbor.get_attr_value(NM.LLDP_ATTR_IEEE_802_1_PPVIDS)
    if port_vlans:
        port_vlans = port_vlans.unpack()
        for p_vlan in port_vlans:
            port_vlan_objects.append(p_vlan[NM_PPVLAN_ID_KEY])
        if port_vlan_objects:
            port_vlans_info[
                LLDP.Neighbors.TLV_TYPE
            ] = ORGANIZATION_SPECIFIC_TLV
            port_vlans_info[LLDP.Neighbors.ORGANIZATION_CODE] = IEEE
            port_vlans_info[LLDP.Neighbors.TLV_SUBTYPE] = PORT_VLAN_SUBTYPE_TLV
            port_vlans_info[NM.LLDP_ATTR_IEEE_802_1_PPVIDS] = port_vlan_objects
            info.append(port_vlans_info)


def _add_neighbor_management_addresses(neighbor, info):
    addresses_objects = []
    addresses_info = {}
    mngt_addresses = neighbor.get_attr_value(NM.LLDP_ATTR_MANAGEMENT_ADDRESSES)
    if mngt_addresses:
        mngt_addresses = mngt_addresses.unpack()
        for mngt_address in mngt_addresses:
            mngt_address_info = {}
            addr, addr_type = _decode_management_address_type(
                mngt_address[NM_MANAGEMENT_ADDR_TYPE_KEY],
                mngt_address[NM_MANAGEMENT_ADDR_KEY],
            )
            mngt_address_info[NM_MANAGEMENT_ADDR_KEY] = addr
            mngt_address_info[NM_MANAGEMENT_ADDR_TYPE_KEY] = addr_type
            mngt_address_info[
                NM_MANAGEMENT_ADDR_IFACE_NUMBER_KEY
            ] = mngt_address[NM_MANAGEMENT_ADDR_IFACE_NUMBER_KEY]
            mngt_address_info[
                NM_MANAGEMENT_ADDR_IFACE_NUMBER_TYPE_KEY
            ] = mngt_address[NM_MANAGEMENT_ADDR_IFACE_NUMBER_TYPE_KEY]
            addresses_objects.append(mngt_address_info)
        if addresses_objects:
            addresses_info[LLDP.Neighbors.TLV_TYPE] = MANAGEMENT_ADDRESSES_TLV
            addresses_info[
                NM.LLDP_ATTR_MANAGEMENT_ADDRESSES
            ] = addresses_objects
            info.append(addresses_info)


def _add_max_frame_size(neighbor, info):
    mfs = neighbor.get_attr_value(NM.LLDP_ATTR_IEEE_802_3_MAX_FRAME_SIZE)
    if mfs:
        mfs_object = {
            LLDP.Neighbors.TLV_TYPE: ORGANIZATION_SPECIFIC_TLV,
            LLDP.Neighbors.ORGANIZATION_CODE: IEEE_802_3,
            LLDP.Neighbors.TLV_SUBTYPE: MFS_SUBTYPE_TLV,
            NM.LLDP_ATTR_IEEE_802_3_MAX_FRAME_SIZE: mfs.get_uint32(),
        }
        info.append(mfs_object)


def _decode_management_address_type(code, address):
    if code == NM_MANAGEMENT_ADDR_TYPE_IPV4:
        addr = ".".join(map(str, address))
        addr_type = "ipv4"
    elif code == NM_MANAGEMENT_ADDR_TYPE_MAC:
        addr = ":".join(["{:02X}".format(octet) for octet in address])
        addr_type = "MAC"
    else:
        addr = ":".join(["{:04X}".format(octet) for octet in address])
        addr_type = "ipv6"

    return addr, addr_type
