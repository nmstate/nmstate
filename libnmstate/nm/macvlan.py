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

from libnmstate.error import NmstateValueError
from libnmstate.schema import MacVlan
from .common import NM


NMSTATE_MODE_TO_NM_MODE = {
    MacVlan.Mode.VEPA: NM.SettingMacvlanMode.VEPA,
    MacVlan.Mode.BRIDGE: NM.SettingMacvlanMode.BRIDGE,
    MacVlan.Mode.PRIVATE: NM.SettingMacvlanMode.PRIVATE,
    MacVlan.Mode.PASSTHRU: NM.SettingMacvlanMode.PASSTHRU,
    MacVlan.Mode.SOURCE: NM.SettingMacvlanMode.SOURCE,
}


def create_setting(iface_state, base_con_profile):
    macvlan = iface_state.get(MacVlan.CONFIG_SUBTREE)
    if not macvlan:
        return None

    macvlan_setting = None
    if base_con_profile:
        macvlan_setting = base_con_profile.get_setting_by_name(
            NM.SETTING_MACVLAN_SETTING_NAME
        )
        if macvlan_setting:
            macvlan_setting = macvlan_setting.duplicate()

    if not macvlan_setting:
        macvlan_setting = NM.SettingMacvlan.new()

    nm_mode = NMSTATE_MODE_TO_NM_MODE.get(macvlan[MacVlan.MODE])
    if not nm_mode or nm_mode == MacVlan.Mode.SOURCE:
        raise NmstateValueError(
            f"{macvlan[MacVlan.MODE]} is not valid or supported by "
            "NetworkManager"
        )

    macvlan_setting.props.mode = nm_mode
    macvlan_setting.props.parent = macvlan[MacVlan.BASE_IFACE]
    if macvlan.get(MacVlan.PROMISCUOUS) is not None:
        macvlan_setting.props.promiscuous = macvlan[MacVlan.PROMISCUOUS]

    return macvlan_setting
