#
# Copyright (c) 2019 Red Hat, Inc.
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

        sriov_setting.props.total_vfs = sriov_config[Ethernet.SRIOV.TOTAL_VFS]

    return sriov_setting


def _has_sriov_capability(ifname):
    dev = device.get_device_by_name(ifname)
    if nmclient.NM.DeviceCapabilities.SRIOV & dev.props.capabilities:
        return True

    return False


def get_info(device):
    """
    Provide the current active SR-IOV live configuration for a device
    """
    info = {}

    connection = nm_connection.ConnectionProfile()
    connection.import_by_device(device)
    if not connection.profile:
        return info

    sriov_setting = connection.profile.get_setting_by_name(
        nmclient.NM.SETTING_SRIOV_SETTING_NAME
    )

    if sriov_setting:
        info[Ethernet.SRIOV_SUBTREE] = {
            Ethernet.SRIOV.TOTAL_VFS: sriov_setting.props.total_vfs
        }

    return info
