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

import re
import subprocess

from libnmstate.error import NmstateNotSupportedError
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

SRIOV_NMSTATE_TO_REGEX = {
    Ethernet.SRIOV.VFS.MAC_ADDRESS: re.compile(
        r"[a-fA-F0-9:]{17}|[a-fA-F0-9]{12}"
    ),
    Ethernet.SRIOV.VFS.SPOOF_CHECK: re.compile(r"checking (on|off)"),
    Ethernet.SRIOV.VFS.TRUST: re.compile(r"trust (on|off)"),
    Ethernet.SRIOV.VFS.MIN_TX_RATE: re.compile(r"min_tx_rate ([0-9]+)"),
    Ethernet.SRIOV.VFS.MAX_TX_RATE: re.compile(r"max_tx_rate ([0-9]+)"),
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
    Provide the current active SR-IOV runtime values
    """
    sriov_running_info = {}

    ifname = device.get_iface()
    numvf_path = f"/sys/class/net/{ifname}/device/sriov_numvfs"
    try:
        with open(numvf_path) as f:
            sriov_running_info[Ethernet.SRIOV.TOTAL_VFS] = int(f.read())
    except FileNotFoundError:
        return sriov_running_info

    if sriov_running_info[Ethernet.SRIOV.TOTAL_VFS]:
        sriov_running_info[Ethernet.SRIOV.VFS_SUBTREE] = _get_sriov_vfs_info(
            ifname
        )
    else:
        sriov_running_info[Ethernet.SRIOV.VFS_SUBTREE] = []

    return {Ethernet.SRIOV_SUBTREE: sriov_running_info}


def _get_sriov_vfs_info(ifname):
    """
    This is a workaround to get the VFs configuration from runtime.
    Ref: https://bugzilla.redhat.com/1777520
    """
    proc = subprocess.run(
        ("ip", "link", "show", ifname),
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    iplink_output = proc.stdout

    # This is ignoring the first two line of the ip link output because they
    # are about the PF and we don't need them.
    vfs = iplink_output.splitlines(False)[2:]
    vfs_config = [
        vf_config for vf_config in _parse_ip_link_output_for_vfs(vfs)
    ]

    return vfs_config


def _parse_ip_link_output_for_vfs(vfs):
    for vf_id, vf in enumerate(vfs):
        vf_config = _parse_ip_link_output_options_for_vf(vf)
        vf_config[Ethernet.SRIOV.VFS.ID] = vf_id
        yield vf_config


def _parse_ip_link_output_options_for_vf(vf):
    vf_options = {}
    for option, expr in SRIOV_NMSTATE_TO_REGEX.items():
        match_expr = expr.search(vf)
        if match_expr:
            if option == Ethernet.SRIOV.VFS.MAC_ADDRESS:
                value = match_expr.group(0)
            else:
                value = match_expr.group(1)

            if value.isdigit():
                value = int(value)
            elif value == "on":
                value = True
            elif value == "off":
                value = False
            vf_options[option] = value

    return vf_options
