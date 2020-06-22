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

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .base_iface import BaseIface
from .bond import BondIface
from .dummy import DummyIface
from .ethernet import EthernetIface
from .linux_bridge import LinuxBridgeIface
from .ovs import OvsBridgeIface
from .ovs import OvsInternalIface
from .team import TeamIface
from .vlan import VlanIface
from .vxlan import VxlanIface


class Ifaces:
    """
    The Ifaces class hold both desired state(optional) and current state.
    When desire state been provided, will perpare the state for backend plugin
    to apply with:
        * Validating on original desire state.
        * Merging state.
        * Generating metadata.
    The class itself is focusing on tasks related to inter-interfaces changes:
        * Mater/slave interfaces.
        * Parent/Child interfaces.
    The class is maitnaing a list of BaseIface(or its child classes) which does
    not know desire state and current state difference. Hence this class is
    also responsible to handle desire vs current state related tasks.
    """

    def __init__(self, des_iface_infos, cur_iface_infos, save_to_disk=True):
        self._save_to_disk = save_to_disk
        self._des_iface_infos = des_iface_infos
        self._cur_ifaces = {}
        self._ifaces = {}
        if cur_iface_infos:
            for iface_info in cur_iface_infos:
                cur_iface = _to_specific_iface_obj(iface_info, save_to_disk)
                self._ifaces[cur_iface.name] = cur_iface
                self._cur_ifaces[cur_iface.name] = cur_iface

        if des_iface_infos:
            for iface_info in des_iface_infos:
                iface = BaseIface(iface_info, save_to_disk)
                cur_iface = self._ifaces.get(iface.name)
                if cur_iface and cur_iface.is_desired:
                    raise NmstateValueError(
                        f"Duplicate interfaces names detected: {iface.name}"
                    )

                if iface_info.get(Interface.TYPE) is None:
                    if cur_iface:
                        iface_info[Interface.TYPE] = cur_iface.type
                    elif iface.is_up:
                        raise NmstateValueError(
                            f"Interface {iface.name} has no type defined "
                            "neither in desire state nor current state"
                        )
                iface = _to_specific_iface_obj(iface_info, save_to_disk)
                if (
                    iface.type == InterfaceType.UNKNOWN
                    # Allowing deletion of down profiles
                    and not iface.is_absent
                ):
                    # Ignore interface with unknown type
                    continue
                if cur_iface:
                    iface.merge(cur_iface)
                iface.mark_as_desired()
                self._ifaces[iface.name] = iface

            self._create_virtual_slaves()
            self._validate_unknown_slaves()
            self._validate_unknown_parent()
            self._gen_metadata()
            for iface in self._ifaces.values():
                iface.pre_edit_validation_and_cleanup()

            self._pre_edit_validation_and_cleanup()

    def _create_virtual_slaves(self):
        """
        Certain master interface could have virtual slaves which does not
        defined in desired state. Create it before generating metadata.
        For example, OVS bridge could have slave defined as OVS internal
        interface which could be created without defining in desire state but
        only in slave list of OVS bridge.
        """
        new_ifaces = []
        for iface in self._ifaces.values():
            if iface.is_up and iface.is_master:
                for slave_name in iface.slaves:
                    if slave_name not in self._ifaces.keys():
                        new_slave = iface.create_virtual_slave(slave_name)
                        if new_slave:
                            new_ifaces.append(new_slave)
        for iface in new_ifaces:
            self._ifaces[iface.name] = iface

    def _pre_edit_validation_and_cleanup(self):
        self._validate_over_booked_slaves()
        self._validate_vlan_mtu()
        self._handle_master_slave_list_change()
        self._match_child_iface_state_with_parent()
        self._mark_orphen_as_absent()
        self._bring_slave_up_if_not_in_desire()
        self._validate_ovs_patch_peers()
        self._remove_unknown_type_interfaces()

    def _bring_slave_up_if_not_in_desire(self):
        """
        When slave been included in master, automactially set it as state UP
        if not defiend in desire state
        """
        for iface in self._ifaces.values():
            if iface.is_up and iface.is_master:
                for slave_name in iface.slaves:
                    slave_iface = self._ifaces[slave_name]
                    if not slave_iface.is_desired and not slave_iface.is_up:
                        slave_iface.mark_as_up()
                        slave_iface.mark_as_changed()

    def _validate_ovs_patch_peers(self):
        """
        When OVS patch peer does not exist or is down, raise an error.
        """
        for iface in self._ifaces.values():
            if iface.type == InterfaceType.OVS_INTERFACE and iface.is_up:
                if iface.peer:
                    peer_iface = self._ifaces.get(iface.peer)
                    if not peer_iface or not peer_iface.is_up:
                        raise NmstateValueError(
                            f"OVS patch port peer {iface.peer} must exist and "
                            "be up"
                        )
                    elif (
                        not peer_iface.type == InterfaceType.OVS_INTERFACE
                        or not peer_iface.is_patch_port
                    ):
                        raise NmstateValueError(
                            f"OVS patch port peer {iface.peer} must be an OVS"
                            " patch port"
                        )

    def _validate_vlan_mtu(self):
        """
        Validate that mtu of vlan or vxlan is less than
        or equal to it's base interface's MTU

        If base MTU is not present, set same as vlan MTU
        """
        for iface in self._ifaces.values():

            if (
                iface.type in [InterfaceType.VLAN, InterfaceType.VXLAN]
                and iface.is_up
                and iface.mtu
            ):
                base_iface = self._ifaces.get(iface.parent)
                if not base_iface.mtu:
                    base_iface.mtu = iface.mtu
                if iface.mtu > base_iface.mtu:
                    raise NmstateValueError(
                        f"Interface {iface.name} has bigger "
                        f"MTU({iface.mtu}) "
                        f"than its base interface: {iface.parent} "
                        f"MTU({base_iface.mtu})"
                    )

    def _handle_master_slave_list_change(self):
        """
         * Mark slave interface as changed if master removed.
         * Mark slave interface as changed if slave list of master changed.
         * Mark slave interface as changed if slave config changed when master
           said so.
        """
        for iface in self._ifaces.values():
            if not iface.is_desired or not iface.is_master:
                continue
            des_slaves = set(iface.slaves)
            if iface.is_absent:
                des_slaves = set()
            cur_iface = self._cur_ifaces.get(iface.name)
            cur_slaves = set(cur_iface.slaves) if cur_iface else set()
            if des_slaves != cur_slaves:
                changed_slaves = (des_slaves | cur_slaves) - (
                    des_slaves & cur_slaves
                )
                for iface_name in changed_slaves:
                    self._ifaces[iface_name].mark_as_changed()
            if cur_iface:
                for slave_name in iface.config_changed_slaves(cur_iface):
                    self._ifaces[slave_name].mark_as_changed()

    def _match_child_iface_state_with_parent(self):
        for iface in self._ifaces.values():
            if iface.parent and self._ifaces.get(iface.parent):
                parent_iface = self._ifaces[iface.parent]
                if parent_iface.is_desired or parent_iface.is_changed:
                    iface.state = parent_iface.state
                    iface.mark_as_changed()

    def _mark_orphen_as_absent(self):
        for iface in self._ifaces.values():
            if iface.need_parent and (
                not iface.parent or not self._ifaces.get(iface.parent)
            ):
                iface.mark_as_changed()
                iface.state = InterfaceState.ABSENT

    def get(self, iface_name):
        return self._ifaces.get(iface_name)

    def __getitem__(self, iface_name):
        return self._ifaces[iface_name]

    def __setitem__(self, iface_name, iface):
        self._ifaces[iface_name] = iface

    def _gen_metadata(self):
        for iface in self._ifaces.values():
            # Generate metadata for all interface in case any of them
            # been marked as changed by DNS/Route/RouteRule.
            iface.gen_metadata(self)

    def keys(self):
        for iface in self._ifaces.keys():
            yield iface

    def values(self):
        for iface in self._ifaces.values():
            yield iface

    @property
    def current_ifaces(self):
        return self._cur_ifaces

    @property
    def state_to_edit(self):
        return [
            iface.to_dict()
            for iface in self._ifaces.values()
            if iface.is_changed or iface.is_desired
        ]

    @property
    def cur_ifaces(self):
        return self._cur_ifaces

    def _remove_unmanaged_slaves(self):
        """
        When master containing unmanaged slaves, they should be removed from
        master slave list.
        """
        for iface in self._ifaces.values():
            if iface.is_up and iface.is_master and iface.slaves:
                for slave_name in iface.slaves:
                    slave_iface = self._ifaces[slave_name]
                    if not slave_iface.is_up:
                        iface.remove_slave(slave_name)

    def verify(self, cur_iface_infos):
        cur_ifaces = Ifaces(
            des_iface_infos=None,
            cur_iface_infos=cur_iface_infos,
            save_to_disk=self._save_to_disk,
        )
        for iface in self._ifaces.values():
            if iface.is_desired:
                if iface.is_up or (iface.is_down and not iface.is_virtual):
                    cur_iface = cur_ifaces.get(iface.name)
                    if not cur_iface:
                        raise NmstateVerificationError(
                            format_desired_current_state_diff(
                                iface.original_dict, {}
                            )
                        )
                    elif not iface.match(cur_iface):
                        raise NmstateVerificationError(
                            format_desired_current_state_diff(
                                iface.state_for_verify(),
                                cur_iface.state_for_verify(),
                            )
                        )

    def gen_dns_metadata(self, dns_state, route_state):
        iface_metadata = dns_state.gen_metadata(self, route_state)
        for iface_name, dns_metadata in iface_metadata.items():
            self._ifaces[iface_name].store_dns_metadata(dns_metadata)
            if dns_state.config_changed:
                self._ifaces[iface_name].mark_as_changed()

    def gen_route_metadata(self, route_state):
        iface_metadata = route_state.gen_metadata(self)
        for iface_name, route_metadata in iface_metadata.items():
            self._ifaces[iface_name].store_route_metadata(route_metadata)

    def gen_route_rule_metadata(self, route_rule_state, route_state):
        iface_metadata = route_rule_state.gen_metadata(route_state)
        for iface_name, route_rule_metadata in iface_metadata.items():
            self._ifaces[iface_name].store_route_rule_metadata(
                route_rule_metadata
            )
            if route_rule_state.config_changed:
                self._ifaces[iface_name].mark_as_changed()

    def _validate_unknown_slaves(self):
        """
        Check the existance of slave interface
        """
        for iface in self._ifaces.values():
            for slave_name in iface.slaves:
                if not self._ifaces.get(slave_name):
                    raise NmstateValueError(
                        f"Interface {iface.name} has unknown slave: "
                        f"{slave_name}"
                    )

    def _validate_unknown_parent(self):
        """
        Check the existance of parent interface
        """
        for iface in self._ifaces.values():
            if iface.parent and not self._ifaces.get(iface.parent):
                raise NmstateValueError(
                    f"Interface {iface.name} has unknown parent: "
                    f"{iface.parent}"
                )

    def _remove_unknown_type_interfaces(self):
        """
        Remove unknown type interfaces that are set as up.
        """
        for iface in list(self._ifaces.values()):
            if iface.type == InterfaceType.UNKNOWN and iface.is_up:
                self._ifaces.pop(iface.name, None)
                logging.debug(
                    f"Interface {iface.name} is type {iface.type} and "
                    "will be ignored during the activation"
                )

    def _validate_over_booked_slaves(self):
        """
        Check whether any slave is used by more than one master
        """
        slave_master_map = {}
        for iface in self._ifaces.values():
            for slave_name in iface.slaves:
                cur_master = slave_master_map.get(slave_name)
                if cur_master:
                    raise NmstateValueError(
                        f"Interface {iface.name} slave {slave_name} is "
                        f"already enslaved by interface {cur_master}"
                    )
                else:
                    slave_master_map[slave_name] = iface.name


def _to_specific_iface_obj(info, save_to_disk):
    iface_type = info.get(Interface.TYPE, InterfaceType.UNKNOWN)
    if iface_type == InterfaceType.ETHERNET:
        return EthernetIface(info, save_to_disk)
    elif iface_type == InterfaceType.BOND:
        return BondIface(info, save_to_disk)
    elif iface_type == InterfaceType.DUMMY:
        return DummyIface(info, save_to_disk)
    elif iface_type == InterfaceType.LINUX_BRIDGE:
        return LinuxBridgeIface(info, save_to_disk)
    elif iface_type == InterfaceType.OVS_BRIDGE:
        return OvsBridgeIface(info, save_to_disk)
    elif iface_type == InterfaceType.OVS_INTERFACE:
        return OvsInternalIface(info, save_to_disk)
    elif iface_type == InterfaceType.VLAN:
        return VlanIface(info, save_to_disk)
    elif iface_type == InterfaceType.VXLAN:
        return VxlanIface(info, save_to_disk)
    elif iface_type == InterfaceType.TEAM:
        return TeamIface(info, save_to_disk)
    else:
        return BaseIface(info, save_to_disk)
