#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from libnmstate.error import NmstateNotSupportedError
from libnmstate.nm import connection as nm_connection
from libnmstate.nm import device
from libnmstate.nm import nmclient
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface


SRIOV_NMSTATE_TO_NM_MAP = {
    Ethernet.SRIOV.VFS.MAC_ADDRESS: (
        nmclient.NM.SRIOV_VF_ATTRIBUTE_MAC,
        nmclient.GLib.Variant.new_string,
    ),
    Ethernet.SRIOV.VFS.SPOOF_CHECK: (
        nmclient.NM.SRIOV_VF_ATTRIBUTE_SPOOF_CHECK,
        nmclient.GLib.Variant.new_boolean,
    ),
    Ethernet.SRIOV.VFS.TRUST: (
        nmclient.NM.SRIOV_VF_ATTRIBUTE_TRUST,
        nmclient.GLib.Variant.new_boolean,
    ),
    Ethernet.SRIOV.VFS.MIN_TX_RATE: (
        nmclient.NM.SRIOV_VF_ATTRIBUTE_MIN_TX_RATE,
        nmclient.GLib.Variant.new_uint32,
    ),
    Ethernet.SRIOV.VFS.MAX_TX_RATE: (
        nmclient.NM.SRIOV_VF_ATTRIBUTE_MAX_TX_RATE,
        nmclient.GLib.Variant.new_uint32,
    ),
}

SRIOV_NM_TO_NMSTATE_MAP = {
    nmclient.NM.SRIOV_VF_ATTRIBUTE_MAC: (
        Ethernet.SRIOV.VFS.MAC_ADDRESS,
        nmclient.GLib.Variant.get_string,
    ),
    nmclient.NM.SRIOV_VF_ATTRIBUTE_SPOOF_CHECK: (
        Ethernet.SRIOV.VFS.SPOOF_CHECK,
        nmclient.GLib.Variant.get_boolean,
    ),
    nmclient.NM.SRIOV_VF_ATTRIBUTE_TRUST: (
        Ethernet.SRIOV.VFS.TRUST,
        nmclient.GLib.Variant.get_boolean,
    ),
    nmclient.NM.SRIOV_VF_ATTRIBUTE_MIN_TX_RATE: (
        Ethernet.SRIOV.VFS.MIN_TX_RATE,
        nmclient.GLib.Variant.get_uint32,
    ),
    nmclient.NM.SRIOV_VF_ATTRIBUTE_MAX_TX_RATE: (
        Ethernet.SRIOV.VFS.MAX_TX_RATE,
        nmclient.GLib.Variant.get_uint32,
    ),
}


def create_setting(iface_state, base_con_profile):
    sriov_setting = None
    ifname = iface_state[Interface.NAME]
    sriov_config = iface_state.get(Ethernet.CONFIG_SUBTREE, {}).get(
        Ethernet.SRIOV_SUBTREE
    )
    if sriov_config:
        if not _has_sriov_capability(ifname):
            raise NmstateNotSupportedError(
                f"Interface '{ifname}' does not support SR-IOV"
            )

        sriov_setting = base_con_profile.get_setting_duplicate(
            nmclient.NM.SETTING_SRIOV_SETTING_NAME
        )
        if not sriov_setting:
            sriov_setting = nmclient.NM.SettingSriov.new()

        vfs_config = sriov_config.get(Ethernet.SRIOV.VFS_SUBTREE, [])
        vf_object_ids = {vf.get_index() for vf in sriov_setting.props.vfs}
        vf_config_ids = {
            vf_config[Ethernet.SRIOV.VFS.ID] for vf_config in vfs_config
        }

        # As the user must do full edit of vfs, nmstate is deleting all the vfs
        # and then adding all the vfs from the config.
        for vf_id in _remove_sriov_vfs_in_setting(
            vfs_config, sriov_setting, vf_object_ids
        ):
            sriov_setting.remove_vf_by_index(vf_id)

        for vf_object in _create_sriov_vfs_from_config(
            vfs_config, sriov_setting, vf_config_ids
        ):
            sriov_setting.add_vf(vf_object)

        sriov_setting.props.total_vfs = sriov_config[Ethernet.SRIOV.TOTAL_VFS]

    return sriov_setting


def _create_sriov_vfs_from_config(vfs_config, sriov_setting, vf_ids_to_add):
    vfs_config_to_add = (
        vf_config
        for vf_config in vfs_config
        if vf_config[Ethernet.SRIOV.VFS.ID] in vf_ids_to_add
    )
    for vf_config in vfs_config_to_add:
        vf_id = vf_config.pop(Ethernet.SRIOV.VFS.ID)
        vf_object = nmclient.NM.SriovVF.new(vf_id)
        for key, val in vf_config.items():
            _set_nm_attribute(vf_object, key, val)

        yield vf_object


def _set_nm_attribute(vf_object, key, value):
    nm_attr, nm_variant = SRIOV_NMSTATE_TO_NM_MAP[key]
    vf_object.set_attribute(nm_attr, nm_variant(value))


def _remove_sriov_vfs_in_setting(vfs_config, sriov_setting, vf_ids_to_remove):
    for vf_id in vf_ids_to_remove:
        yield vf_id


def _has_sriov_capability(ifname):
    dev = device.get_device_by_name(ifname)
    if nmclient.NM.DeviceCapabilities.SRIOV & dev.props.capabilities:
        return True

    return False


def get_info(device):
    """
    Provide the current active SR-IOV total-vfs runtime value and the live
    configuration for each VF for a device.
    """
    info = {}
    sriov_config = {}

    ifname = device.get_iface()
    numvf_path = f"/sys/class/net/{ifname}/device/sriov_numvfs"
    try:
        with open(numvf_path) as f:
            sriov_config[Ethernet.SRIOV.TOTAL_VFS] = int(f.read())
    except FileNotFoundError:
        return info

    connection = nm_connection.ConnectionProfile()
    connection.import_by_device(device)
    if not connection.profile:
        info[Ethernet.SRIOV_SUBTREE] = sriov_config
        return info

    sriov_setting = connection.profile.get_setting_by_name(
        nmclient.NM.SETTING_SRIOV_SETTING_NAME
    )

    if sriov_setting:
        vfs_config = _get_info_sriov_vfs_config(sriov_setting)
        sriov_config[Ethernet.SRIOV.VFS_SUBTREE] = vfs_config

        info[Ethernet.SRIOV_SUBTREE] = sriov_config

    return info


def _get_info_sriov_vfs_config(sriov_setting):
    vfs_config = []
    vfs_setting = sriov_setting.props.vfs
    for vf in vfs_setting:
        vf_config = {}
        vf_config[Ethernet.SRIOV.VFS.ID] = vf.get_index()
        for nm_attribute in SRIOV_NM_TO_NMSTATE_MAP.keys():
            _get_nm_attribute(vf, vf_config, nm_attribute)

        vfs_config.append(vf_config)

    return vfs_config


def _get_nm_attribute(vf_object, vf_config, nm_attribute):
    nmstate_key, nm_variant = SRIOV_NM_TO_NMSTATE_MAP[nm_attribute]
    if vf_object.get_attribute(nm_attribute) is not None:
        vf_config[nmstate_key] = nm_variant(
            vf_object.get_attribute(nm_attribute)
        )
