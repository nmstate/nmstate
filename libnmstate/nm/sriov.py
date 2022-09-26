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

from libnmstate.schema import Ethernet

from .common import NM
from .common import GLib


SRIOV_NMSTATE_TO_NM_MAP = {
    Ethernet.SRIOV.VFS.MAC_ADDRESS: (
        NM.SRIOV_VF_ATTRIBUTE_MAC,
        GLib.Variant.new_string,
    ),
    Ethernet.SRIOV.VFS.SPOOF_CHECK: (
        NM.SRIOV_VF_ATTRIBUTE_SPOOF_CHECK,
        GLib.Variant.new_boolean,
    ),
    Ethernet.SRIOV.VFS.TRUST: (
        NM.SRIOV_VF_ATTRIBUTE_TRUST,
        GLib.Variant.new_boolean,
    ),
    Ethernet.SRIOV.VFS.MIN_TX_RATE: (
        NM.SRIOV_VF_ATTRIBUTE_MIN_TX_RATE,
        GLib.Variant.new_uint32,
    ),
    Ethernet.SRIOV.VFS.MAX_TX_RATE: (
        NM.SRIOV_VF_ATTRIBUTE_MAX_TX_RATE,
        GLib.Variant.new_uint32,
    ),
}


def create_setting(iface, base_con_profile):
    sriov_setting = None
    sriov_config = iface.original_desire_dict.get(
        Ethernet.CONFIG_SUBTREE, {}
    ).get(Ethernet.SRIOV_SUBTREE)

    if base_con_profile:
        sriov_setting = base_con_profile.get_setting_by_name(
            NM.SETTING_SRIOV_SETTING_NAME
        )
    if sriov_config:
        if sriov_setting:
            sriov_setting = sriov_setting.duplicate()
        else:
            sriov_setting = NM.SettingSriov.new()

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
        vf_object = NM.SriovVF.new(vf_id)
        for key, val in vf_config.items():
            _set_nm_attribute(vf_object, key, val)

        vlan_id = vf_config.get(Ethernet.SRIOV.VFS.VLAN_ID)
        vlan_qos = vf_config.get(Ethernet.SRIOV.VFS.QOS)
        if vlan_id:
            vf_object.add_vlan(vlan_id)
            if vlan_qos:
                vf_object.set_vlan_qos(vlan_id, vlan_qos)

        yield vf_object


def _set_nm_attribute(vf_object, key, value):
    if key in SRIOV_NMSTATE_TO_NM_MAP:
        nm_attr, nm_variant = SRIOV_NMSTATE_TO_NM_MAP[key]
        vf_object.set_attribute(nm_attr, nm_variant(value))


def _remove_sriov_vfs_in_setting(vfs_config, sriov_setting, vf_ids_to_remove):
    for vf_id in vf_ids_to_remove:
        yield vf_id
