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
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import MacVlan
from libnmstate.schema import MacVtap
from .common import NM


NMSTATE_MODE_TO_NM_MODE = {
    MacVlan.Mode.VEPA: NM.SettingMacvlanMode.VEPA,
    MacVlan.Mode.BRIDGE: NM.SettingMacvlanMode.BRIDGE,
    MacVlan.Mode.PRIVATE: NM.SettingMacvlanMode.PRIVATE,
    MacVlan.Mode.PASSTHRU: NM.SettingMacvlanMode.PASSTHRU,
    MacVlan.Mode.SOURCE: NM.SettingMacvlanMode.SOURCE,
}


def create_setting(iface_state, base_con_profile, tap=False):
    macvlan = (
        iface_state.get(MacVtap.CONFIG_SUBTREE)
        if tap
        else iface_state.get(MacVlan.CONFIG_SUBTREE)
    )
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
    macvlan_setting.props.tap = tap
    if macvlan.get(MacVlan.PROMISCUOUS) is not None:
        macvlan_setting.props.promiscuous = macvlan[MacVlan.PROMISCUOUS]

    return macvlan_setting


def get_current_macvlan_type(applied_config):
    """
    This is a workaround needed due to Nmstate gathering the interface type
    from NetworkManager, as we are deciding the interface type using the
    setting name. If the interface type is not adjusted, Nmstate will fail
    during verification as NM and Nispor interfaces will not be merged
    correctly.
    """
    if applied_config:
        macvlan_setting = applied_config.get_setting_by_name(
            NM.SETTING_MACVLAN_SETTING_NAME
        )
        if macvlan_setting:
            tap = macvlan_setting.props.tap
            if tap:
                return {Interface.TYPE: InterfaceType.MAC_VTAP}
    return {}
