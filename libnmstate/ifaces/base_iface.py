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

from collections.abc import Mapping
from copy import deepcopy
import logging
from operator import itemgetter

from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateValueError
from libnmstate.iplib import is_ipv6_link_local_addr
from libnmstate.iplib import canonicalize_ip_address
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import LLDP

from ..state import state_match
from ..state import merge_dict


class IPState:
    def __init__(self, family, info):
        self._family = family
        self._info = info
        self._remove_stack_if_disabled()
        self._sort_addresses()
        self._canonicalize_ip_addr()
        self._canonicalize_dynamic()

    def _canonicalize_dynamic(self):
        if self.is_enabled and self.is_dynamic:
            self._info[InterfaceIP.ADDRESS] = []
            self._info.setdefault(InterfaceIP.AUTO_ROUTES, True)
            self._info.setdefault(InterfaceIP.AUTO_DNS, True)
            self._info.setdefault(InterfaceIP.AUTO_GATEWAY, True)
        else:
            for dhcp_option in (
                InterfaceIP.AUTO_ROUTES,
                InterfaceIP.AUTO_GATEWAY,
                InterfaceIP.AUTO_DNS,
            ):
                self._info.pop(dhcp_option, None)

    def _canonicalize_ip_addr(self):
        for addr in self.addresses:
            addr[InterfaceIP.ADDRESS_IP] = canonicalize_ip_address(
                addr[InterfaceIP.ADDRESS_IP]
            )

    def _sort_addresses(self):
        self.addresses.sort(key=itemgetter(InterfaceIP.ADDRESS_IP))

    def _remove_stack_if_disabled(self):
        if not self.is_enabled:
            self._info = {InterfaceIP.ENABLED: False}

    @property
    def is_enabled(self):
        return self._info.get(InterfaceIP.ENABLED, False)

    @property
    def is_dynamic(self):
        return self._info.get(InterfaceIP.DHCP) or self._info.get(
            InterfaceIPv6.AUTOCONF
        )

    @property
    def auto_dns(self):
        return self.is_dynamic and self._info.get(InterfaceIP.AUTO_DNS)

    @property
    def addresses(self):
        return self._info.get(InterfaceIP.ADDRESS, [])

    def to_dict(self):
        return deepcopy(self._info)

    def validate(self, original):
        if (
            self.is_enabled
            and self.is_dynamic
            and original.addresses
            and self.addresses
        ):
            logging.warning(
                f"Static addresses {original.addresses} "
                "are ignored when dynamic IP is enabled"
            )

    def remove_link_local_address(self):
        if self.addresses:
            self._info[InterfaceIP.ADDRESS] = [
                addr
                for addr in self.addresses
                if not is_ipv6_link_local_addr(
                    addr[InterfaceIP.ADDRESS_IP],
                    addr[InterfaceIP.ADDRESS_PREFIX_LENGTH],
                )
            ]


class BaseIface:
    MASTER_METADATA = "_master"
    MASTER_TYPE_METADATA = "_master_type"
    DNS_METADATA = "_dns"
    ROUTES_METADATA = "_routes"
    ROUTE_RULES_METADATA = "_route_rules"

    def __init__(self, info, save_to_disk=True):
        self._origin_info = deepcopy(info)
        self._info = deepcopy(info)
        self._is_desired = False
        self._is_changed = False
        self._name = self._info[Interface.NAME]
        self._save_to_disk = save_to_disk

    @property
    def can_have_ip_when_enslaved(self):
        return False

    def sort_slaves(self):
        pass

    @property
    def raw(self):
        """
        Internal use only: Allowing arbitrary modifcation.
        """
        return self._info

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._info.get(Interface.TYPE, InterfaceType.UNKNOWN)

    @property
    def state(self):
        return self._info.get(Interface.STATE, InterfaceState.UP)

    @state.setter
    def state(self, value):
        self._info[Interface.STATE] = value

    @property
    def is_desired(self):
        return self._is_desired

    @property
    def is_changed(self):
        return self._is_changed

    def mark_as_changed(self):
        self._is_changed = True

    def mark_as_desired(self):
        self._is_desired = True

    def to_dict(self):
        return deepcopy(self._info)

    @property
    def original_dict(self):
        return self._origin_info

    def ip_state(self, family):
        return IPState(family, self._info.get(family, {}))

    def is_ipv4_enabled(self):
        return self.ip_state(Interface.IPV4).is_enabled

    def is_ipv6_enabled(self):
        return self.ip_state(Interface.IPV6).is_enabled

    def is_dynamic(self, family):
        return self.ip_state(family).is_dynamic

    def pre_edit_validation_and_cleanup(self):
        """
        This function is called after metadata generation finished.
        Will do
         * Raise NmstateValueError when user desire(self.original_dict) is
           illegal.
         * Clean up illegal setting introduced by merging.
        We don't split validation from clean up as they might sharing the same
        check code.
        """
        if self.is_desired:
            for family in (Interface.IPV4, Interface.IPV6):
                self.ip_state(family).validate(
                    IPState(family, self._origin_info.get(family, {}))
                )
            self._validate_slave_ip()
            ip_state = self.ip_state(family)
            ip_state.remove_link_local_address()
            self._info[family] = ip_state.to_dict()
            if self.is_absent and not self._save_to_disk:
                self._info[Interface.STATE] = InterfaceState.DOWN

    def merge(self, other):
        merge_dict(self._info, other._info)

    def _validate_slave_ip(self):
        for family in (Interface.IPV4, Interface.IPV6):
            ip_state = IPState(family, self._origin_info.get(family, {}))
            if (
                ip_state.is_enabled
                and self.master
                and not self.can_have_ip_when_enslaved
            ):
                raise NmstateValueError(
                    f"Interface {self.name} is enslaved by {self.master_type} "
                    f"interface {self.master} which does not allow "
                    f"slaves to have {family} enabled"
                )

    @property
    def slaves(self):
        return []

    @property
    def parent(self):
        return None

    @property
    def need_parent(self):
        return False

    @property
    def is_absent(self):
        return self.state == InterfaceState.ABSENT

    @property
    def is_up(self):
        return self.state == InterfaceState.UP

    @property
    def is_down(self):
        return self.state == InterfaceState.DOWN

    def mark_as_up(self):
        self.raw[Interface.STATE] = InterfaceState.UP

    @property
    def is_master(self):
        return False

    def set_master(self, master_iface_name, master_type):
        self._info[BaseIface.MASTER_METADATA] = master_iface_name
        self._info[BaseIface.MASTER_TYPE_METADATA] = master_type
        if not self.can_have_ip_when_enslaved:
            for family in (Interface.IPV4, Interface.IPV6):
                self._info[family] = {InterfaceIP.ENABLED: False}

    @property
    def master(self):
        return self._info.get(BaseIface.MASTER_METADATA)

    @property
    def master_type(self):
        return self._info.get(BaseIface.MASTER_TYPE_METADATA)

    def gen_metadata(self, ifaces):
        if self.is_master and not self.is_absent:
            for slave_name in self.slaves:
                slave_iface = ifaces[slave_name]
                slave_iface.set_master(self.name, self.type)

    def update(self, info):
        self._info.update(info)

    @property
    def mac(self):
        return self._info.get(Interface.MAC)

    @property
    def mtu(self):
        return self._info.get(Interface.MTU)

    @mtu.setter
    def mtu(self, value):
        self._info[Interface.MTU] = value

    def _capitalize_mac(self):
        if self.mac:
            self._info[Interface.MAC] = self.mac.upper()

    def match(self, other):
        self_state = self.state_for_verify()
        other_state = other.state_for_verify()
        return state_match(self_state, other_state)

    def state_for_verify(self):
        """
        Return the network state as dictionary used for verifcation.
        Clean up if required.
        For BaseIface:
            * Capitalize MAC addresses.
            * Explicitly set state as UP if not defined.
            * Remove IPv6 link local addresses.
            * Remove empty description.
        """
        self._capitalize_mac()
        self.sort_slaves()
        for family in (Interface.IPV4, Interface.IPV6):
            ip_state = self.ip_state(family)
            ip_state.remove_link_local_address()
            self._info[family] = ip_state.to_dict()
        state = self.to_dict()
        _remove_empty_description(state)
        _remove_undesired_data(state, self.original_dict)
        _remove_lldp_neighbors(state)
        if Interface.STATE not in state:
            state[Interface.STATE] = InterfaceState.UP
        if self.is_absent and not self._save_to_disk:
            state[Interface.STATE] = InterfaceState.DOWN

        return state

    def remove_slave(self, slave_name):
        if not self.is_master:
            class_name = self.__class__.__name__
            raise NmstateInternalError(
                f"Invalid invoke of {class_name}.remove_slave({slave_name}) "
                f"as {class_name} is not a master interface"
            )

    @property
    def is_virtual(self):
        return False

    def create_virtual_slave(self, slave_name):
        """
        When master interface has non-exist slave interface, master should
        create virtual slave for this name if possible, or else return None
        """
        return None

    def config_changed_slaves(self, _cur_iface):
        """
        Return a list of slave interface name which has configuration changed
        compareing to cur_iface.
        """
        return []

    def store_dns_metadata(self, dns_metadata):
        for family, dns_config in dns_metadata.items():
            self.raw[family][BaseIface.DNS_METADATA] = dns_config

    def remove_dns_metadata(self):
        for family in (Interface.IPV4, Interface.IPV6):
            self.raw.get(family, {}).pop(BaseIface.DNS_METADATA, None)

    def store_route_metadata(self, route_metadata):
        for family, routes in route_metadata.items():
            self.raw[family][BaseIface.ROUTES_METADATA] = routes

    def store_route_rule_metadata(self, route_rule_metadata):
        for family, rules in route_rule_metadata.items():
            self.raw[family][BaseIface.ROUTE_RULES_METADATA] = rules


def _remove_empty_description(state):
    if state.get(Interface.DESCRIPTION) == "":
        del state[Interface.DESCRIPTION]


def _remove_lldp_neighbors(state):
    state.get(LLDP.CONFIG_SUBTREE, {}).pop(LLDP.NEIGHBORS_SUBTREE, None)


def _remove_undesired_data(state, desire):
    """
    For any key not defined in `desire`, remove it from `state`
    """
    key_to_remove = []
    for key, value in state.items():
        if key not in desire:
            key_to_remove.append(key)
        elif isinstance(value, Mapping):
            _remove_undesired_data(value, desire[key])
    for key in key_to_remove:
        state.pop(key)
