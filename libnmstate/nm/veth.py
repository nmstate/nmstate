#
# Copyright (c) 2021 Red Hat, Inc.
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
from libnmstate.ifaces.veth import VethIface
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Veth
from .common import NM


SETTING_VETH = "SettingVeth"
SETTING_VETH_SETTING_NAME = "SETTING_VETH_SETTING_NAME"


def create_setting(iface, base_con_profile):
    veth_setting = None

    if not is_nm_veth_supported():
        raise NmstateNotSupportedError(
            "Configuring veth interfaces is only supported on NetworkManager "
            "1.30 or greater."
        )

    if base_con_profile:
        veth_setting = base_con_profile.get_setting_by_name(
            getattr(NM, SETTING_VETH_SETTING_NAME)
        )
        if veth_setting:
            veth_setting = veth_setting.duplicate()

    if not veth_setting:
        veth_setting = getattr(NM, SETTING_VETH).new()
    veth_setting.props.peer = iface.peer

    return veth_setting


def is_nm_veth_supported():
    return hasattr(NM, SETTING_VETH_SETTING_NAME)


def is_veth(applied_config):
    if applied_config and is_nm_veth_supported():
        veth_setting = applied_config.get_setting_by_name(
            getattr(NM, SETTING_VETH_SETTING_NAME)
        )
        if veth_setting:
            return True

    return False


def get_current_veth_type(applied_config):
    """
    This is a workaround needed due to Nmstate gathering interface type from
    NetworkManager, as NetworkManager is exposing veth interfaces as ethernet.
    If the interface type is not adjusted, Nmstate will fail during
    verification as NM and Nispor interfaces will not be merged correctly.
    """
    if is_veth(applied_config):
        return {Interface.TYPE: InterfaceType.VETH}
    return {}


def create_iface_for_nm_veth_peer(iface):
    return VethIface(
        {
            Interface.NAME: iface.peer,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.VETH,
            Veth.CONFIG_SUBTREE: {Veth.PEER: iface.name},
        }
    )
