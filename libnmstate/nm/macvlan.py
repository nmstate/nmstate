#
# Copyright (c) 2020-2021 Red Hat, Inc.
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
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import MacVlan
from .common import NM


NMSTATE_MODE_TO_NM_MODE = {
    MacVlan.Mode.VEPA: NM.SettingMacvlanMode.VEPA,
    MacVlan.Mode.BRIDGE: NM.SettingMacvlanMode.BRIDGE,
    MacVlan.Mode.PRIVATE: NM.SettingMacvlanMode.PRIVATE,
    MacVlan.Mode.PASSTHRU: NM.SettingMacvlanMode.PASSTHRU,
    MacVlan.Mode.SOURCE: NM.SettingMacvlanMode.SOURCE,
}


def create_setting(iface, base_con_profile, tap=False):
    macvlan_setting = None
    if base_con_profile:
        macvlan_setting = base_con_profile.get_setting_by_name(
            NM.SETTING_MACVLAN_SETTING_NAME
        )
        if macvlan_setting:
            macvlan_setting = macvlan_setting.duplicate()

    if not macvlan_setting:
        macvlan_setting = NM.SettingMacvlan.new()

    nm_mode = NMSTATE_MODE_TO_NM_MODE.get(iface.mode)
    if not nm_mode or nm_mode == MacVlan.Mode.SOURCE:
        raise NmstateValueError(
            f"{iface.mode} is not valid or supported by " "NetworkManager"
        )

    macvlan_setting.props.mode = nm_mode
    macvlan_setting.props.parent = iface.base_iface
    macvlan_setting.props.tap = tap
    if iface.promiscuous is not None:
        macvlan_setting.props.promiscuous = iface.promiscuous

    return macvlan_setting


def is_macvtap(applied_config):
    if applied_config:
        macvlan_setting = applied_config.get_setting_by_name(
            NM.SETTING_MACVLAN_SETTING_NAME
        )
        if macvlan_setting:
            return macvlan_setting.props.tap
    return False


def get_current_macvlan_type(applied_config):
    """
    This is a workaround needed due to Nmstate gathering the interface type
    from NetworkManager, as we are deciding the interface type using the
    setting name. If the interface type is not adjusted, Nmstate will fail
    during verification as NM and Nispor interfaces will not be merged
    correctly.
    """
    if is_macvtap(applied_config):
        return {Interface.TYPE: InterfaceType.MAC_VTAP}
    return {}
