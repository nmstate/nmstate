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

import logging

from libnmstate.schema import InfiniBand
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from .common import NM

_NM_IB_MODE_DATAGRAM = "datagram"
_NM_IB_MODE_CONNECTED = "connected"


def get_info(applied_config):
    if applied_config:
        ib_setting = applied_config.get_setting_infiniband()
        if ib_setting:
            mode = _nm_ib_mode_to_nmstate(ib_setting.get_transport_mode())
            if not mode:
                logging.warning(
                    "Unknown InfiniBand transport mode "
                    f"{ib_setting.get_transport_mode()} for interface "
                    f"{applied_config.get_interface_name()}"
                )
                return {}

            pkey = ib_setting.get_p_key()
            if pkey == -1:
                pkey = str(InfiniBand.DEFAULT_PKEY)
            else:
                pkey = hex(pkey)

            base_iface = ib_setting.get_parent()
            if base_iface is None:
                base_iface = ""

            return {
                Interface.TYPE: InterfaceType.INFINIBAND,
                InfiniBand.CONFIG_SUBTREE: {
                    InfiniBand.PKEY: pkey,
                    InfiniBand.MODE: mode,
                    InfiniBand.BASE_IFACE: base_iface,
                },
            }
    return {}


def _nm_ib_mode_to_nmstate(nm_ib_mode):
    if nm_ib_mode == _NM_IB_MODE_DATAGRAM:
        return InfiniBand.Mode.DATAGRAM
    elif nm_ib_mode == _NM_IB_MODE_CONNECTED:
        return InfiniBand.Mode.CONNECTED
    else:
        return None


def create_setting(iface_info, base_con_profile, original_iface_info):
    ib_config = iface_info.get(InfiniBand.CONFIG_SUBTREE)
    if not ib_config:
        return None

    ib_setting = None
    if base_con_profile:
        ib_setting = base_con_profile.get_setting_infiniband()
        if ib_setting:
            ib_setting = ib_setting.duplicate()

    if not ib_setting:
        ib_setting = NM.SettingInfiniband.new()

    if Interface.MTU in original_iface_info:
        ib_setting.props.mtu = original_iface_info[Interface.MTU]
    if Interface.MAC in original_iface_info:
        ib_setting.props.mac_address = original_iface_info[Interface.MAC]

    if ib_config[InfiniBand.PKEY] == InfiniBand.DEFAULT_PKEY:
        ib_setting.props.p_key = -1
    else:
        ib_setting.props.p_key = ib_config[InfiniBand.PKEY]
    ib_setting.props.transport_mode = ib_config[InfiniBand.MODE]

    if InfiniBand.BASE_IFACE in ib_config:
        if ib_config[InfiniBand.BASE_IFACE]:
            ib_setting.props.parent = ib_config[InfiniBand.BASE_IFACE]
        else:
            ib_setting.props.parent = None

    return ib_setting
