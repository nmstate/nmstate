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

from copy import deepcopy
from operator import itemgetter

from libnmstate.error import NmstateValueError
from libnmstate.schema import Bridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import OVSBridge
from libnmstate.schema import OVSInterface
from libnmstate.validator import validate_boolean
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_string

from .bridge import BridgeIface
from .base_iface import BaseIface


SYSTEMCTL_TIMEOUT_SECONDS = 5

VALID_VLAN_FILTERING_MODES = [
    Bridge.Port.Vlan.Mode.ACCESS,
    Bridge.Port.Vlan.Mode.TRUNK,
    Bridge.Port.Vlan.Mode.UNKNOWN,
]


class OvsBridgeIface(BridgeIface):
    @property
    def is_user_space_only(self):
        return True

    @property
    def _has_bond_port(self):
        for port_config in self.port_configs:
            if port_config.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE):
                return True
        return False

    def sort_port(self):
        super().sort_port()
        self._sort_bond_port()

    def _sort_bond_port(self):
        # For port of ovs bond/link_aggregation
        for port in self.port_configs:
            port_cfg = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if port_cfg:
                port_cfg.get(
                    OVSBridge.Port.LinkAggregation.PORT_SUBTREE, []
                ).sort(
                    key=itemgetter(OVSBridge.Port.LinkAggregation.Port.NAME)
                )

    @property
    def port(self):
        port = []
        for port_config in self.port_configs:
            lag = port_config.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag:
                lag_port = lag.get(
                    OVSBridge.Port.LinkAggregation.PORT_SUBTREE, []
                )
                name_key = OVSBridge.Port.LinkAggregation.Port.NAME
                port += [s[name_key] for s in lag_port]
            else:
                port.append(port_config[OVSBridge.Port.NAME])
        return port

    def gen_metadata(self, ifaces):
        for ovs_iface_name in self.port:
            ovs_iface = ifaces.all_kernel_ifaces[ovs_iface_name]
            ovs_iface_config = _lookup_ovs_iface_config(
                self.port_configs, ovs_iface_name
            )
            ovs_iface.update(
                {BridgeIface.BRPORT_OPTIONS_METADATA: ovs_iface_config}
            )
            if ovs_iface.type == InterfaceType.OVS_INTERFACE:
                ovs_iface.parent = self.name
        super().gen_metadata(ifaces)

    def create_virtual_port(self, port_name):
        """
        When port does not exists in merged desire state, it means it's an
        OVS internal interface, create it.
        """
        port_iface = OvsInternalIface(
            {
                Interface.NAME: port_name,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                Interface.STATE: InterfaceState.UP,
            }
        )
        port_iface.mark_as_changed()
        port_iface.set_controller(self.name, self.type)
        port_iface.parent = self.name
        return port_iface

    def pre_edit_validation_and_cleanup(self):
        self._validate_ovs_properties()
        super().pre_edit_validation_and_cleanup()
        if self.is_up:
            self._validate_ovs_lag_port_count()

    def _validate_ovs_properties(self):
        for port_info in self.port_configs:
            validate_string(port_info.get(Bridge.Port.NAME), Bridge.Port.NAME)
            vlan_filtering_info = port_info.get(Bridge.Port.VLAN_SUBTREE)
            if vlan_filtering_info:
                validate_string(
                    vlan_filtering_info.get(Bridge.Port.Vlan.MODE),
                    Bridge.Port.Vlan.MODE,
                    VALID_VLAN_FILTERING_MODES,
                )
                validate_boolean(
                    vlan_filtering_info.get(Bridge.Port.Vlan.ENABLE_NATIVE),
                    Bridge.Port.Vlan.ENABLE_NATIVE,
                )
                validate_integer(
                    vlan_filtering_info.get(Bridge.Port.Vlan.TAG),
                    Bridge.Port.Vlan.TAG,
                    minimum=0,
                    maximum=4095,
                )
            link_aggregation = port_info.get(
                OVSBridge.Port.LINK_AGGREGATION_SUBTREE
            )
            if link_aggregation:
                validate_string(
                    link_aggregation.get(OVSBridge.Port.LinkAggregation.MODE),
                    OVSBridge.Port.LinkAggregation.MODE,
                )

        options_info = self._info.get(Bridge.OPTIONS_SUBTREE)
        if options_info:
            validate_boolean(
                options_info.get(OVSBridge.Options.STP), OVSBridge.Options.STP
            )
            validate_boolean(
                options_info.get(OVSBridge.Options.RSTP),
                OVSBridge.Options.RSTP,
            )
            validate_boolean(
                options_info.get(OVSBridge.Options.MCAST_SNOOPING_ENABLED),
                OVSBridge.Options.MCAST_SNOOPING_ENABLED,
            )
            validate_string(
                options_info.get(OVSBridge.Options.FAIL_MODE),
                OVSBridge.Options.FAIL_MODE,
            )
            validate_string(
                options_info.get(OVSBridge.Options.DATAPATH),
                OVSBridge.Options.DATAPATH,
                ("system", "netdev", ""),
            )

    def _validate_ovs_lag_port_count(self):
        for port in self.port_configs:
            port_subtree = OVSBridge.Port.LinkAggregation.PORT_SUBTREE
            lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag and len(lag.get(port_subtree, ())) < 2:
                raise NmstateValueError(
                    f"OVS {self.name} LAG port {lag} has less than 2 port."
                )

    def remove_port(self, port_name):
        new_port_configs = []
        for port in self.port_configs:
            if port[OVSBridge.Port.NAME] == port_name:
                continue
            lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag:
                new_port = deepcopy(port)
                new_lag = new_port[OVSBridge.Port.LINK_AGGREGATION_SUBTREE]
                lag_port = lag.get(OVSBridge.Port.LinkAggregation.PORT_SUBTREE)
                if lag_port:
                    name_key = OVSBridge.Port.LinkAggregation.Port.NAME
                    new_lag[OVSBridge.Port.LinkAggregation.PORT_SUBTREE] = [
                        s for s in lag_port if s[name_key] != port_name
                    ]
                new_port_configs.append(new_port)
            else:
                new_port_configs.append(port)
        self.raw[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] = new_port_configs
        self.sort_port()


def _lookup_ovs_iface_config(bridge_port_configs, ovs_iface_name):
    for port_config in bridge_port_configs:
        lag_state = port_config.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
        if lag_state and _is_ovs_lag_port(lag_state, ovs_iface_name):
            return port_config
        elif port_config[OVSBridge.Port.NAME] == ovs_iface_name:
            return port_config
    return {}


def _is_ovs_lag_port(lag_state, iface_name):
    port = lag_state.get(OVSBridge.Port.LinkAggregation.PORT_SUBTREE, ())
    for port_member in port:
        if port_member[OVSBridge.Port.LinkAggregation.Port.NAME] == iface_name:
            return True
    return False


class OvsInternalIface(BaseIface):
    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._parent = None

    @property
    def is_virtual(self):
        return True

    @property
    def can_have_ip_as_port(self):
        return True

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @property
    def need_parent(self):
        return True

    @property
    def patch_config(self):
        return self._info.get(OVSInterface.PATCH_CONFIG_SUBTREE, {})

    @property
    def is_patch_port(self):
        return self.patch_config and self.patch_config.get(
            OVSInterface.Patch.PEER
        )

    @property
    def dpdk_config(self):
        return self._info.get(OVSInterface.DPDK_CONFIG_SUBTREE, {})

    @property
    def is_dpdk(self):
        return self.dpdk_config and self.dpdk_config.get(
            OVSInterface.Dpdk.DEVARGS
        )

    @property
    def devargs(self):
        return (
            self.dpdk_config.get(OVSInterface.Dpdk.DEVARGS)
            if self.dpdk_config
            else None
        )

    @property
    def peer(self):
        return (
            self.patch_config.get(OVSInterface.Patch.PEER)
            if self.patch_config
            else None
        )

    def pre_edit_validation_and_cleanup(self):
        validate_string(
            self.patch_config.get(OVSInterface.Patch.PEER),
            OVSInterface.Patch.PEER,
        )
        validate_string(
            self.patch_config.get(OVSInterface.Dpdk.DEVARGS),
            OVSInterface.Dpdk.DEVARGS,
        )
        super().pre_edit_validation_and_cleanup()
        self._validate_ovs_mtu_mac_confliction()

    def _validate_ovs_mtu_mac_confliction(self):
        if self.is_patch_port:
            if (
                self.original_desire_dict.get(Interface.IPV4, {}).get(
                    InterfaceIP.ENABLED
                )
                or self.original_desire_dict.get(Interface.IPV6, {}).get(
                    InterfaceIP.ENABLED
                )
                or self.original_desire_dict.get(Interface.MTU)
                or self.original_desire_dict.get(Interface.MAC)
            ):
                raise NmstateValueError(
                    "OVS Patch interface cannot contain MAC address, MTU"
                    " or IP configuration."
                )
            else:
                self._info.pop(Interface.MTU, None)
                self._info.pop(Interface.MAC, None)


def is_ovs_lag_port(port_state):
    return port_state.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE) is not None


class OvsPortIface(BaseIface):
    def __init__(self, info, save_to_disk=True):
        super().__init__(info, save_to_disk)
        self._parent = None

    @property
    def is_user_space_only(self):
        return True
