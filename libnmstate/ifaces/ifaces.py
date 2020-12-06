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

from libnmstate.error import NmstateKernelIntegerRoundedError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateNotSupportedError
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .base_iface import BaseIface
from .bond import BondIface
from .dummy import DummyIface
from .ethernet import EthernetIface
from .infiniband import InfiniBandIface
from .linux_bridge import LinuxBridgeIface
from .macvlan import MacVlanIface
from .macvtap import MacVtapIface
from .ovs import OvsBridgeIface
from .ovs import OvsInternalIface
from .team import TeamIface
from .vlan import VlanIface
from .vxlan import VxlanIface
from .vrf import VrfIface


class _UserSpaceIfaces:
    def __init__(self):
        self._ifaces = {}

    def set(self, iface):
        self._ifaces[f"{iface.name}.{iface.type}"] = iface

    def get(self, iface_name, iface_type):
        return self._ifaces.get(f"{iface_name}.{iface_type}")

    def remove(self, iface):
        if self.get(iface.name, iface.type):
            del self._ifaces[f"{iface.name}.{iface.type}"]

    def __iter__(self):
        for iface in self._ifaces.values():
            yield iface


class Ifaces:
    """
    The Ifaces class hold both desired state(optional) and current state.
    When desire state been provided, will perpare the state for backend plugin
    to apply with:
        * Validating on original desire state.
        * Merging state.
        * Generating metadata.
    The class itself is focusing on tasks related to inter-interfaces changes:
        * Mater/port interfaces.
        * Parent/Child interfaces.
    The class is maitnaing a list of BaseIface(or its child classes) which does
    not know desire state and current state difference. Hence this class is
    also responsible to handle desire vs current state related tasks.
    """

    def __init__(self, des_iface_infos, cur_iface_infos, save_to_disk=True):
        self._save_to_disk = save_to_disk
        self._des_iface_infos = des_iface_infos
        self._cur_kernel_ifaces = {}
        self._kernel_ifaces = {}
        self._user_space_ifaces = _UserSpaceIfaces()
        self._cur_user_space_ifaces = _UserSpaceIfaces()
        self._ignored_ifaces = set()
        if cur_iface_infos:
            for iface_info in cur_iface_infos:
                cur_iface = _to_specific_iface_obj(iface_info, save_to_disk)
                if cur_iface.is_user_space_only:
                    self._user_space_ifaces.set(cur_iface)
                    self._cur_user_space_ifaces.set(cur_iface)
                else:
                    self._kernel_ifaces[cur_iface.name] = cur_iface
                    self._cur_kernel_ifaces[cur_iface.name] = cur_iface

        if des_iface_infos:
            for iface_info in des_iface_infos:
                iface = BaseIface(iface_info, save_to_disk)
                if iface.type == InterfaceType.UNKNOWN:
                    cur_ifaces = self._get_cur_ifaces(iface.name)
                    if len(cur_ifaces) > 1:
                        raise NmstateValueError(
                            f"Got multiple interface with name {iface.name}, "
                            "please specify the interface type explicitly"
                        )
                cur_iface = self.get_iface(iface.name, iface.type)
                if cur_iface and cur_iface.is_desired:
                    raise NmstateValueError(
                        f"Duplicate interfaces names detected: {iface.name} "
                        f"for type {cur_iface.type}"
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
                if iface.is_ignore:
                    self._ignored_ifaces.add(
                        (iface.name, iface.type, iface.is_user_space_only)
                    )
                if cur_iface:
                    iface.merge(cur_iface)
                iface.mark_as_desired()
                if iface.is_user_space_only:
                    self._user_space_ifaces.set(iface)
                else:
                    self._kernel_ifaces[iface.name] = iface

            self._create_virtual_port()
            self._validate_unknown_port()
            self._validate_unknown_parent()
            self._validate_infiniband_as_bridge_port()
            self._validate_infiniband_as_bond_port()
            self._gen_metadata()
            for iface in self.all_ifaces():
                iface.pre_edit_validation_and_cleanup()

            self._pre_edit_validation_and_cleanup()

    def _create_virtual_port(self):
        """
        Certain controller interface could have virtual port which does not
        defined in desired state. Create it before generating metadata.
        For example, OVS bridge could have port defined as OVS internal
        interface which could be created without defining in desire state but
        only in port list of OVS bridge.
        """
        new_ifaces = []
        for iface in self.all_ifaces():
            if iface.is_up and iface.is_controller:
                for port_name in iface.port:
                    # nmstate does not support port interface to be user
                    # space interface
                    if port_name not in self._kernel_ifaces.keys():
                        new_port = iface.create_virtual_port(port_name)
                        if new_port:
                            new_ifaces.append(new_port)
        for iface in new_ifaces:
            self._kernel_ifaces[iface.name] = iface

    def _pre_edit_validation_and_cleanup(self):
        self._validate_over_booked_port()
        self._validate_vlan_not_over_infiniband()
        self._validate_vlan_mtu()
        self._handle_controller_port_list_change()
        self._match_child_iface_state_with_parent()
        self._mark_orphan_as_absent()
        self._bring_port_up_if_not_in_desire()
        self._validate_ovs_patch_peers()
        self._remove_unknown_type_interfaces()
        self._validate_vrf_table_id_changes()

    def _bring_port_up_if_not_in_desire(self):
        """
        When port been included in controller, automactially set it as state UP
        if not defiend in desire state
        """
        for iface in self.all_ifaces():
            if iface.is_up and iface.is_controller:
                for port_name in iface.port:
                    port_iface = self._kernel_ifaces[port_name]
                    if not port_iface.is_desired and not port_iface.is_up:
                        port_iface.mark_as_up()
                        port_iface.mark_as_changed()

    def _validate_ovs_patch_peers(self):
        """
        When OVS patch peer does not exist or is down, raise an error.
        """
        for iface in self._kernel_ifaces.values():
            if iface.type == InterfaceType.OVS_INTERFACE and iface.is_up:
                if iface.peer:
                    peer_iface = self._kernel_ifaces.get(iface.peer)
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

    def _validate_vlan_not_over_infiniband(self):
        """
        Validate that vlan is not being created over infiniband interface
        """
        for iface in self._kernel_ifaces.values():

            if (
                iface.type in [InterfaceType.VLAN, InterfaceType.VXLAN]
                and iface.is_up
            ):
                if (
                    self._kernel_ifaces[iface.parent].type
                    == InterfaceType.INFINIBAND
                ):
                    raise NmstateValueError(
                        f"Interface {iface.name} of type {iface.type}"
                        " is not supported over base interface of "
                        "type Infiniband"
                    )

    def _validate_vlan_mtu(self):
        """
        Validate that mtu of vlan or vxlan is less than
        or equal to it's base interface's MTU

        If base MTU is not present, set same as vlan MTU
        """
        for iface in self._kernel_ifaces.values():

            if (
                iface.type in [InterfaceType.VLAN, InterfaceType.VXLAN]
                and iface.is_up
                and iface.mtu
            ):
                base_iface = self._kernel_ifaces.get(iface.parent)
                if not base_iface.mtu:
                    base_iface.mtu = iface.mtu
                if iface.mtu > base_iface.mtu:
                    raise NmstateValueError(
                        f"Interface {iface.name} has bigger "
                        f"MTU({iface.mtu}) "
                        f"than its base interface: {iface.parent} "
                        f"MTU({base_iface.mtu})"
                    )

    def _validate_infiniband_as_bridge_port(self):
        """
        The IPoIB NIC has no ethernet layer, hence is no way for adding a IPoIB
        NIC to linux bridge or OVS bridge
        """
        for iface in self.all_ifaces():
            if iface.is_desired and iface.type in (
                InterfaceType.LINUX_BRIDGE,
                InterfaceType.OVS_BRIDGE,
            ):
                for port_name in iface.port:
                    port_iface = self._kernel_ifaces[port_name]
                    if port_iface.type == InterfaceType.INFINIBAND:
                        raise NmstateValueError(
                            f"The bridge {iface.name} cannot use "
                            f"IP over InfiniBand interface {port_iface.name} "
                            f"as port. Please use RoCE interface instead."
                        )

    def _validate_infiniband_as_bond_port(self):
        """
        The IP over InfiniBand interface is only allowed to be port of
        bond in "active-backup" mode.
        """
        for iface in self._kernel_ifaces.values():
            if (
                iface.is_desired
                and iface.type == InterfaceType.BOND
                and iface.bond_mode != BondMode.ACTIVE_BACKUP
            ):
                for port_name in iface.port:
                    port_iface = self._kernel_ifaces[port_name]
                    if port_iface.type == InterfaceType.INFINIBAND:
                        raise NmstateValueError(
                            "The IP over InfiniBand interface "
                            f"{port_iface.name} is only allowed to be port of "
                            "bond in active-backup mode, but requested bond "
                            f"{iface.name} is in {iface.bond_mode} mode."
                        )

    def _handle_controller_port_list_change(self):
        """
        * Mark port interface as changed if controller removed.
        * Mark port interface as changed if port list of controller changed.
        * Mark port interface as changed if port config changed when
          controller said so.
        """
        for iface in self.all_ifaces():
            if not iface.is_desired or not iface.is_controller:
                continue
            des_port = set(iface.port)
            if iface.is_absent:
                des_port = set()
            cur_iface = self.get_cur_iface(iface.name, iface.type)
            cur_port = set(cur_iface.port) if cur_iface else set()
            if des_port != cur_port:
                changed_port = (des_port | cur_port) - (des_port & cur_port)
                for iface_name in changed_port:
                    self._kernel_ifaces[iface_name].mark_as_changed()
            if cur_iface:
                for port_name in iface.config_changed_port(cur_iface):
                    if port_name in self._kernel_ifaces:
                        self._kernel_ifaces[port_name].mark_as_changed()

    def _validate_vrf_table_id_changes(self):
        for iface in self._kernel_ifaces.values():
            if iface.is_desired and iface.type == InterfaceType.VRF:
                cur_iface = self._cur_kernel_ifaces.get(iface.name)
                if (
                    cur_iface
                    and cur_iface.route_table_id != iface.route_table_id
                ):
                    raise NmstateNotSupportedError(
                        "Changing route table ID of existing VRF Interface "
                        "is not supported yet"
                    )

    def _match_child_iface_state_with_parent(self):
        """
        Handles these use cases:
            * When changed/desired parent interface is up, child is not
              desired to be any state, set child as UP.
            * When changed/desired parent interface is marked as down or
              absent, child state should sync with parent.
        """
        for iface in self.all_ifaces():
            if iface.parent:
                parent_iface = self._get_parent_iface(iface)
                if (
                    parent_iface
                    and parent_iface.is_desired
                    or parent_iface.is_changed
                ):
                    if (
                        Interface.STATE not in iface.original_dict
                        or parent_iface.is_down
                        or parent_iface.is_absent
                    ):
                        iface.state = parent_iface.state
                        iface.mark_as_changed()

    def _get_parent_iface(self, iface):
        if not iface.parent:
            return None
        for cur_iface in self.all_ifaces():
            if cur_iface.name == iface.parent and iface != cur_iface:
                return cur_iface
        return None

    def _mark_orphan_as_absent(self):
        for iface in self._kernel_ifaces.values():
            if iface.need_parent and (iface.is_desired or iface.is_changed):
                parent_iface = self._get_parent_iface(iface)
                if parent_iface is None or parent_iface.is_absent:
                    iface.mark_as_changed()
                    iface.state = InterfaceState.ABSENT

    def all_ifaces(self):
        for iface in self._kernel_ifaces.values():
            yield iface
        for iface in self._user_space_ifaces:
            yield iface

    @property
    def all_kernel_ifaces(self):
        """
        Return a editable dict of kernel interfaces, indexed by interface name
        """
        return self._kernel_ifaces

    @property
    def all_user_space_ifaces(self):
        """
        Return a editable user space interfaces, the object has functions:
            * set(iface)
            * get(iface)
            * remove(iface)
            * __iter__()
        """
        return self._user_space_ifaces

    def _get_cur_ifaces(self, iface_name):
        return [
            iface
            for iface in (
                list(self._cur_kernel_ifaces.values())
                + list(self._cur_user_space_ifaces)
            )
            if iface.name == iface_name
        ]

    def get_iface(self, iface_name, iface_type):
        iface = self._kernel_ifaces.get(iface_name)
        if iface and iface_type in (None, InterfaceType.UNKNOWN, iface.type):
            return iface

        for iface in self._user_space_ifaces:
            if iface.name == iface_name and iface_type in (
                None,
                InterfaceType.UNKNOWN,
                iface.type,
            ):
                return iface
        return None

    def get_cur_iface(self, iface_name, iface_type):

        iface = self._cur_kernel_ifaces.get(iface_name)
        if iface and iface_type in (None, InterfaceType.UNKNOWN, iface.type):
            return iface

        for iface in self._cur_user_space_ifaces:
            if iface.name == iface_name and iface_type in (
                None,
                InterfaceType.UNKNOWN,
                iface.type,
            ):
                return iface
        return None

    def _remove_iface(self, iface_name, iface_type):
        cur_iface = self._cur_kernel_ifaces.get(iface_name, iface_type)
        if cur_iface:
            self._user_space_ifaces.remove(cur_iface)
        else:
            cur_iface = self._kernel_ifaces.get(iface_name)
            if (
                iface_type
                and iface_type != InterfaceType.UNKNOWN
                and iface_type == cur_iface.type
            ):
                del self._kernel_ifaces[iface_name]

    def add_ifaces(self, ifaces):
        for iface in ifaces:
            if iface.is_user_space_only:
                self._user_space_ifaces.set(iface)
            else:
                self._kernel_ifaces[iface.name] = iface

    def _gen_metadata(self):
        for iface in self.all_ifaces():
            # Generate metadata for all interface in case any of them
            # been marked as changed by DNS/Route/RouteRule.
            iface.gen_metadata(self)

    @property
    def state_to_edit(self):
        return [
            iface.to_dict()
            for iface in self.all_ifaces()
            if (iface.is_changed or iface.is_desired) and not iface.is_ignore
        ]

    def _remove_unknown_interface_type_port(self):
        """
        When controller containing port with unknown interface type, they
        should be removed from controller port list before verifying.
        """
        for iface in self.all_ifaces():
            if iface.is_up and iface.is_controller and iface.port:
                for port_name in iface.port:
                    port_iface = self._kernel_ifaces[port_name]
                    if port_iface.type == InterfaceType.UNKNOWN:
                        iface.remove_port(port_name)

    def verify(self, cur_iface_infos):
        cur_ifaces = Ifaces(
            des_iface_infos=None,
            cur_iface_infos=cur_iface_infos,
            save_to_disk=self._save_to_disk,
        )
        cur_ifaces._remove_unknown_interface_type_port()
        cur_ifaces._remove_ignore_interfaces(self._ignored_ifaces)
        self._remove_ignore_interfaces(self._ignored_ifaces)
        for iface in self.all_ifaces():
            if iface.is_desired:
                if iface.is_virtual and iface.original_dict.get(
                    Interface.STATE
                ) in (InterfaceState.DOWN, InterfaceState.ABSENT):
                    cur_iface = cur_ifaces.get_iface(iface.name, iface.type)
                    if cur_iface:
                        raise NmstateVerificationError(
                            format_desired_current_state_diff(
                                iface.original_dict,
                                cur_iface.state_for_verify(),
                            )
                        )
                elif iface.is_up or (iface.is_down and not iface.is_virtual):
                    cur_iface = cur_ifaces.get_iface(iface.name, iface.type)
                    if not cur_iface:
                        raise NmstateVerificationError(
                            format_desired_current_state_diff(
                                iface.original_dict, {}
                            )
                        )
                    elif not iface.match(cur_iface):
                        if iface.type == InterfaceType.LINUX_BRIDGE:
                            (
                                key,
                                value,
                                cur_value,
                            ) = LinuxBridgeIface.is_integer_rounded(
                                iface, cur_iface
                            )
                            if key:
                                raise NmstateKernelIntegerRoundedError(
                                    "Linux kernel configured with 250 HZ "
                                    "will round up/down the integer in linux "
                                    f"bridge {iface.name} option '{key}' "
                                    f"from {value} to {cur_value}."
                                )
                        elif iface.type == InterfaceType.BOND:
                            # oVirt who is using nmstate dislike nmstate
                            # raise Exception on bond option mismatch and
                            # they cannot use `verify_change=False` when
                            # changing bond options.
                            if iface.match_ignore_bond_options(cur_iface):
                                continue

                        raise NmstateVerificationError(
                            format_desired_current_state_diff(
                                iface.state_for_verify(),
                                cur_iface.state_for_verify(),
                            )
                        )

    def gen_dns_metadata(self, dns_state, route_state):
        iface_metadata = dns_state.gen_metadata(self, route_state)
        for iface_name, dns_metadata in iface_metadata.items():
            self._kernel_ifaces[iface_name].store_dns_metadata(dns_metadata)
            if dns_state.config_changed:
                self._kernel_ifaces[iface_name].mark_as_changed()

    def gen_route_metadata(self, route_state):
        iface_metadata = route_state.gen_metadata(self)
        for iface_name, route_metadata in iface_metadata.items():
            route_state = route_metadata.pop(
                BaseIface.ROUTE_CHANGED_METADATA, None
            )
            if route_state:
                self._kernel_ifaces[iface_name].mark_as_changed()

            self._kernel_ifaces[iface_name].store_route_metadata(
                route_metadata
            )

    def gen_route_rule_metadata(self, route_rule_state, route_state):
        iface_metadata = route_rule_state.gen_metadata(
            route_state, self._kernel_ifaces
        )
        for iface_name, route_rule_metadata in iface_metadata.items():
            rule_state = route_rule_metadata.pop(
                BaseIface.RULE_CHANGED_METADATA, None
            )
            if rule_state:
                self._kernel_ifaces[iface_name].mark_as_changed()

            self._kernel_ifaces[iface_name].store_route_rule_metadata(
                route_rule_metadata
            )

    def _validate_unknown_port(self):
        """
        Check the existance of port interface
        """
        # All the user space interface already has interface type defined.
        # And user space interface cannot be port of other interface.
        # Hence no need to check `self._user_space_ifaces`
        for iface in self._kernel_ifaces.values():
            for port_name in iface.port:
                if not self._kernel_ifaces.get(port_name):
                    raise NmstateValueError(
                        f"Interface {iface.name} has unknown port: {port_name}"
                    )

    def _validate_unknown_parent(self):
        """
        Check the existance of parent interface
        """
        # All child interface should be in kernel space.
        for iface in self._kernel_ifaces.values():
            if iface.parent:
                parent_iface = self._get_parent_iface(iface)
                if not parent_iface:
                    raise NmstateValueError(
                        f"Interface {iface.name} has unknown parent: "
                        f"{iface.parent}"
                    )

    def _remove_unknown_type_interfaces(self):
        """
        Remove unknown type interfaces that are set as up.
        """
        # All the user space interface already has interface type defined.
        # Hence no need to check `self._user_space_ifaces`
        for iface in list(self._kernel_ifaces.values()):
            if iface.type == InterfaceType.UNKNOWN and iface.is_up:
                self._kernel_ifaces.pop(iface.name, None)
                logging.debug(
                    f"Interface {iface.name} is type {iface.type} and "
                    "will be ignored during the activation"
                )

    def _validate_over_booked_port(self):
        """
        Check whether any port is used by more than one controller
        """
        port_controller_map = {}
        for iface in self.all_ifaces():
            for port_name in iface.port:
                cur_controller = port_controller_map.get(port_name)
                if cur_controller:
                    # Only kernel requires each interface to have
                    # one controller interface at most.
                    cur_controller_iface = self._kernel_ifaces.get(
                        cur_controller
                    )
                    if (
                        cur_controller_iface
                        and not cur_controller_iface.is_absent
                    ):
                        raise NmstateValueError(
                            f"Interface {iface.name} port {port_name} is "
                            f"already as port for interface {cur_controller}"
                        )
                else:
                    port_controller_map[port_name] = iface.name

    def _remove_ignore_interfaces(self, ignored_ifaces):
        for iface_name, iface_type, _ in ignored_ifaces:
            self._remove_iface(iface_name, iface_type)

        # Only kernel interface can be used as port
        ignored_kernel_iface_names = set(
            iface_name
            for iface_name, _, is_user_space_only in ignored_ifaces
            if not is_user_space_only
        )

        # Remove ignored port
        for iface in self.all_ifaces():
            if iface.is_up and iface.is_controller and iface.port:
                for port_name in iface.port:
                    if port_name in ignored_kernel_iface_names:
                        iface.remove_port(port_name)


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
    elif iface_type == InterfaceType.VRF:
        return VrfIface(info, save_to_disk)
    elif iface_type == InterfaceType.INFINIBAND:
        return InfiniBandIface(info, save_to_disk)
    elif iface_type == InterfaceType.MAC_VLAN:
        return MacVlanIface(info, save_to_disk)
    elif iface_type == InterfaceType.MAC_VTAP:
        return MacVtapIface(info, save_to_disk)
    else:
        return BaseIface(info, save_to_disk)
