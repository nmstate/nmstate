#
# Copyright (c) 2018-2021 Red Hat, Inc.
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

import copy

from libnmstate.schema import Bond
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from .common import NM
from .veth import is_nm_veth_supported


class Api2Nm:
    _iface_types_map = None

    @staticmethod
    def get_iface_type(name):
        return Api2Nm.get_iface_type_map().get(name, InterfaceType.UNKNOWN)

    @staticmethod
    def get_iface_type_map():
        if Api2Nm._iface_types_map is None:
            ovs_bridge = InterfaceType.OVS_BRIDGE
            ovs_interface = InterfaceType.OVS_INTERFACE
            Api2Nm._iface_types_map = {
                InterfaceType.ETHERNET: NM.SETTING_WIRED_SETTING_NAME,
                InterfaceType.BOND: NM.SETTING_BOND_SETTING_NAME,
                InterfaceType.DUMMY: NM.SETTING_DUMMY_SETTING_NAME,
                InterfaceType.VLAN: NM.SETTING_VLAN_SETTING_NAME,
                InterfaceType.VXLAN: NM.SETTING_VXLAN_SETTING_NAME,
                InterfaceType.LINUX_BRIDGE: NM.SETTING_BRIDGE_SETTING_NAME,
                InterfaceType.VRF: NM.SETTING_VRF_SETTING_NAME,
                InterfaceType.INFINIBAND: NM.SETTING_INFINIBAND_SETTING_NAME,
                InterfaceType.MAC_VTAP: NM.SETTING_MACVLAN_SETTING_NAME,
                InterfaceType.MAC_VLAN: NM.SETTING_MACVLAN_SETTING_NAME,
                InterfaceType.VETH: Api2Nm._veth_or_ethernet_setting(),
            }
            try:
                ovs_types = {
                    ovs_bridge: NM.SETTING_OVS_BRIDGE_SETTING_NAME,
                    InterfaceType.OVS_PORT: NM.SETTING_OVS_PORT_SETTING_NAME,
                    ovs_interface: NM.SETTING_OVS_INTERFACE_SETTING_NAME,
                }
                Api2Nm._iface_types_map.update(ovs_types)
            except AttributeError:
                pass

        return Api2Nm._iface_types_map

    @staticmethod
    def get_bond_options(iface_desired_state):
        iface_type = Api2Nm.get_iface_type(iface_desired_state[Interface.TYPE])
        if iface_type == InterfaceType.BOND:
            # Is the mode a must config parameter?
            bond_conf = iface_desired_state[Bond.CONFIG_SUBTREE]
            bond_opts = {Bond.MODE: bond_conf[Bond.MODE]}
            bond_opts.update(bond_conf.get(Bond.OPTIONS_SUBTREE, {}))
        else:
            bond_opts = {}

        return bond_opts

    @staticmethod
    def _veth_or_ethernet_setting():
        SETTING_VETH_SETTING_NAME = "SETTING_VETH_SETTING_NAME"

        setting = NM.SETTING_WIRED_SETTING_NAME
        if is_nm_veth_supported():
            setting = getattr(NM, SETTING_VETH_SETTING_NAME)

        return setting


class Nm2Api:
    _iface_types_map = None

    @staticmethod
    def get_common_device_info(devinfo):
        type_name = devinfo["type_name"]
        if type_name != InterfaceType.ETHERNET:
            type_name = Nm2Api.get_iface_type(type_name)
        return {
            Interface.NAME: devinfo[Interface.NAME],
            Interface.TYPE: type_name,
            Interface.STATE: Nm2Api.get_iface_admin_state(
                devinfo[Interface.STATE]
            ),
        }

    @staticmethod
    def get_bond_info(bondinfo):
        bond_options = copy.deepcopy(bondinfo.get(Bond.OPTIONS_SUBTREE))
        if not bond_options:
            return {}
        bond_port = bondinfo[Bond.PORT]

        bond_mode = bond_options[Bond.MODE]
        del bond_options[Bond.MODE]
        return {
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: bond_mode,
                Bond.PORT: [port.props.interface for port in bond_port],
                Bond.OPTIONS_SUBTREE: bond_options,
            }
        }

    @staticmethod
    def get_iface_type(name):
        if Nm2Api._iface_types_map is None:
            Nm2Api._iface_types_map = Nm2Api._swap_dict_keyval(
                Api2Nm.get_iface_type_map()
            )
        return Nm2Api._iface_types_map.get(name, InterfaceType.UNKNOWN)

    @staticmethod
    def get_iface_admin_state(dev_state):
        if NM.DeviceState.IP_CONFIG <= dev_state <= NM.DeviceState.ACTIVATED:
            return InterfaceState.UP
        return InterfaceState.DOWN

    @staticmethod
    def _swap_dict_keyval(dictionary):
        return {val: key for key, val in dictionary.items()}
