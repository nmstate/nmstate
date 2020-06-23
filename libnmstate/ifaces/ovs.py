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

from copy import deepcopy
from operator import itemgetter
import subprocess

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import OVSBridge
from libnmstate.schema import OVSInterface
from libnmstate.schema import OvsDB

from .bridge import BridgeIface
from .base_iface import BaseIface


SYSTEMCTL_TIMEOUT_SECONDS = 5


class OvsBridgeIface(BridgeIface):
    @property
    def _has_bond_port(self):
        for port_config in self.port_configs:
            if port_config.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE):
                return True
        return False

    def sort_slaves(self):
        super().sort_slaves()
        self._sort_bond_slaves()

    def _sort_bond_slaves(self):
        # For slaves of ovs bond/link_aggregation
        for port in self.port_configs:
            lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag:
                lag.get(
                    OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE, []
                ).sort(
                    key=itemgetter(OVSBridge.Port.LinkAggregation.Slave.NAME)
                )

    @property
    def slaves(self):
        slaves = []
        for port_config in self.port_configs:
            lag = port_config.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag:
                lag_slaves = lag.get(
                    OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE, []
                )
                name_key = OVSBridge.Port.LinkAggregation.Slave.NAME
                slaves += [s[name_key] for s in lag_slaves]
            else:
                slaves.append(port_config[OVSBridge.Port.NAME])
        return slaves

    def gen_metadata(self, ifaces):
        for slave_name in self.slaves:
            slave_iface = ifaces[slave_name]
            port_config = _lookup_ovs_port_by_interface(
                self.port_configs, slave_iface.name
            )
            slave_iface.update(
                {BridgeIface.BRPORT_OPTIONS_METADATA: port_config}
            )
            if slave_iface.type == InterfaceType.OVS_INTERFACE:
                slave_iface.parent = self.name
        super().gen_metadata(ifaces)

    def create_virtual_slave(self, slave_name):
        """
        When slave does not exists in merged desire state, it means it's an
        OVS internal interface, create it.
        """
        slave_iface = OvsInternalIface(
            {
                Interface.NAME: slave_name,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                Interface.STATE: InterfaceState.UP,
            }
        )
        slave_iface.mark_as_changed()
        slave_iface.set_master(self.name, self.type)
        slave_iface.parent = self.name
        return slave_iface

    def pre_edit_validation_and_cleanup(self):
        super().pre_edit_validation_and_cleanup()
        self._validate_ovs_lag_slave_count()

    def _validate_ovs_lag_slave_count(self):
        for port in self.port_configs:
            slaves_subtree = OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE
            lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag and len(lag.get(slaves_subtree, ())) < 2:
                raise NmstateValueError(
                    f"OVS {self.name} LAG port {lag} has less than 2 slaves."
                )

    def remove_slave(self, slave_name):
        new_port_configs = []
        for port in self.port_configs:
            if port[OVSBridge.Port.NAME] == slave_name:
                continue
            lag = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
            if lag:
                new_port = deepcopy(port)
                new_lag = new_port[OVSBridge.Port.LINK_AGGREGATION_SUBTREE]
                lag_slaves = lag.get(
                    OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE
                )
                if lag_slaves:
                    name_key = OVSBridge.Port.LinkAggregation.Slave.NAME
                    new_lag[OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE] = [
                        s for s in lag_slaves if s[name_key] != slave_name
                    ]
                new_port_configs.append(new_port)
            else:
                new_port_configs.append(port)
        self.raw[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] = new_port_configs
        self.sort_slaves()

    def state_for_verify(self):
        state = super().state_for_verify()
        _convert_external_ids_values_to_string(state)
        return state


def _lookup_ovs_port_by_interface(ports, slave_name):
    for port in ports:
        lag_state = port.get(OVSBridge.Port.LINK_AGGREGATION_SUBTREE)
        if lag_state and _is_ovs_lag_slave(lag_state, slave_name):
            return port
        elif port[OVSBridge.Port.NAME] == slave_name:
            return port
    return {}


def _is_ovs_lag_slave(lag_state, iface_name):
    slaves = lag_state.get(OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE, ())
    for slave in slaves:
        if slave[OVSBridge.Port.LinkAggregation.Slave.NAME] == iface_name:
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
    def can_have_ip_when_enslaved(self):
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
        return self._info.get(OVSInterface.PATCH_CONFIG_SUBTREE)

    def state_for_verify(self):
        state = super().state_for_verify()
        _convert_external_ids_values_to_string(state)
        return state

    @property
    def is_patch_port(self):
        return self.patch_config and self.patch_config.get(
            OVSInterface.Patch.PEER
        )

    @property
    def peer(self):
        return (
            self.patch_config.get(OVSInterface.Patch.PEER)
            if self.patch_config
            else None
        )

    def pre_edit_validation_and_cleanup(self):
        super().pre_edit_validation_and_cleanup()
        self._validate_ovs_mtu_mac_confliction()

    def _validate_ovs_mtu_mac_confliction(self):
        if self.is_patch_port:
            if (
                self.original_dict.get(Interface.IPV4, {}).get(
                    InterfaceIP.ENABLED
                )
                or self.original_dict.get(Interface.IPV6, {}).get(
                    InterfaceIP.ENABLED
                )
                or self.original_dict.get(Interface.MTU)
                or self.original_dict.get(Interface.MAC)
            ):
                raise NmstateValueError(
                    "OVS Patch interface cannot contain MAC address, MTU"
                    " or IP configuration."
                )
            else:
                self._info.pop(Interface.MTU, None)
                self._info.pop(Interface.MAC, None)


def is_ovs_running():
    try:
        subprocess.run(
            ("systemctl", "status", "openvswitch"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=SYSTEMCTL_TIMEOUT_SECONDS,
        )
        return True
    except Exception:
        return False


def _convert_external_ids_values_to_string(iface_info):
    external_ids = iface_info.get(OvsDB.OVS_DB_SUBTREE, {}).get(
        OvsDB.EXTERNAL_IDS, {}
    )
    for key, value in external_ids.items():
        external_ids[key] = str(value)
