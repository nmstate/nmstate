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
from libnmstate.schema import OvsDB
from libnmstate.schema import Ieee8021X

from ..state import state_match
from ..state import merge_dict


class IPState:
    def __init__(self, family, info):
        self._family = family
        self._info = info
        self._remove_stack_if_disabled()
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

    def sort_addresses(self):
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
    CONTROLLER_METADATA = "_controller"
    CONTROLLER_TYPE_METADATA = "_controller_type"
    DNS_METADATA = "_dns"
    ROUTES_METADATA = "_routes"
    ROUTE_RULES_METADATA = "_route_rules"
    RULE_CHANGED_METADATA = "_changed"
    ROUTE_CHANGED_METADATA = "_changed"

    def __init__(self, info, save_to_disk=True):
        self._origin_info = deepcopy(info)
        self._info = deepcopy(info)
        self._is_desired = False
        self._is_changed = False
        self._name = self._info[Interface.NAME]
        self._save_to_disk = save_to_disk

    @property
    def can_have_ip_as_port(self):
        return False

    @property
    def is_user_space_only(self):
        """
        Whether this interface is user space only.
        User space network interface means:
            * Can have duplicate interface name against kernel network
              interfaces
            * Cannot be used subordinate of other kernel interfaces.
            * Due to limtation of nmstate, currently cannot be used as
              subordinate of other user space interfaces.
        """
        return False

    def sort_port(self):
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

    def mark_as_absent_by_desire(self):
        self.mark_as_desired()
        self._info[Interface.STATE] = InterfaceState.ABSENT
        self._origin_info[Interface.STATE] = InterfaceState.ABSENT

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
            if not self.is_absent:
                for family in (Interface.IPV4, Interface.IPV6):
                    self.ip_state(family).validate(
                        IPState(family, self._origin_info.get(family, {}))
                    )
                self._validate_port_ip()
                ip_state = self.ip_state(family)
                ip_state.remove_link_local_address()
                self._info[family] = ip_state.to_dict()
            if self.is_absent and not self._save_to_disk:
                self._info[Interface.STATE] = InterfaceState.DOWN

    def merge(self, other):
        self._ovsdb_pre_merge_clean_up(other)
        merge_dict(self._info, other._info)
        # If down state is not from orignal state, set it as UP.
        if (
            Interface.STATE not in self._origin_info
            and self.state == InterfaceState.DOWN
        ):
            self._info[Interface.STATE] = InterfaceState.UP

    def _ovsdb_pre_merge_clean_up(self, other):
        """
        * When user not define ovsdb external_ids, we copy from other.
        * When user define ovsdb external_ids, we don't merget from other and
          expecting user to provider full picture.
        """
        desired_external_ids = self._info.get(OvsDB.OVS_DB_SUBTREE, {}).get(
            OvsDB.EXTERNAL_IDS
        )
        current_external_ids = other._info.get(OvsDB.OVS_DB_SUBTREE, {}).get(
            OvsDB.EXTERNAL_IDS
        )
        if desired_external_ids is None:
            if current_external_ids:
                self._info.update(
                    {
                        OvsDB.OVS_DB_SUBTREE: {
                            OvsDB.EXTERNAL_IDS: current_external_ids
                        }
                    }
                )
        else:
            if current_external_ids:
                other._info[OvsDB.OVS_DB_SUBTREE].pop(OvsDB.EXTERNAL_IDS)

    def _validate_port_ip(self):
        for family in (Interface.IPV4, Interface.IPV6):
            ip_state = IPState(family, self._origin_info.get(family, {}))
            if (
                ip_state.is_enabled
                and self.controller
                and self.controller_type != InterfaceType.VRF
                and not self.can_have_ip_as_port
            ):
                raise NmstateValueError(
                    f"Interface {self.name} is port of {self.controller_type} "
                    f"interface {self.controller} which does not allow "
                    f"port to have {family} enabled"
                )

    @property
    def port(self):
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
    def is_ignore(self):
        return self.state == InterfaceState.IGNORE

    @property
    def is_down(self):
        return self.state == InterfaceState.DOWN

    def mark_as_up(self):
        self.raw[Interface.STATE] = InterfaceState.UP

    def mark_as_ignored(self):
        self.raw[Interface.STATE] = InterfaceState.IGNORE

    @property
    def is_controller(self):
        return False

    def set_controller(self, controller_iface_name, controller_type):
        self._info[BaseIface.CONTROLLER_METADATA] = controller_iface_name
        self._info[BaseIface.CONTROLLER_TYPE_METADATA] = controller_type
        if (
            not self.can_have_ip_as_port
            and controller_type != InterfaceType.VRF
        ):
            for family in (Interface.IPV4, Interface.IPV6):
                self._info[family] = {InterfaceIP.ENABLED: False}

    @property
    def controller(self):
        return self._info.get(BaseIface.CONTROLLER_METADATA)

    @property
    def controller_type(self):
        return self._info.get(BaseIface.CONTROLLER_TYPE_METADATA)

    def gen_metadata(self, ifaces):
        if self.is_controller and not self.is_absent:
            for port_name in self.port:
                port_iface = ifaces.all_kernel_ifaces.get(port_name)
                if port_iface:
                    port_iface.set_controller(self.name, self.type)

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
            * Change OVSDB value to string.
        """
        self._capitalize_mac()
        self.sort_port()
        for family in (Interface.IPV4, Interface.IPV6):
            ip_state = self.ip_state(family)
            ip_state.sort_addresses()
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
        _convert_ovs_external_ids_values_to_string(state)

        return state

    def remove_port(self, port_name):
        if not self.is_controller:
            class_name = self.__class__.__name__
            raise NmstateInternalError(
                f"Invalid invoke of {class_name}.remove_port({port_name}) "
                f"as {class_name} is not a controller interface"
            )

    @property
    def is_virtual(self):
        return False

    def create_virtual_port(self, port_name):
        """
        When controller interface has non-exist port interface, controller
        should create virtual port for this name if possible, or else return
        None
        """
        return None

    def config_changed_port(self, _cur_iface):
        """
        Return a list of port interface name which has configuration changed
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
            try:
                self.raw[family][BaseIface.ROUTES_METADATA] = routes
            except KeyError:
                self.raw[family] = {BaseIface.ROUTES_METADATA: routes}

    def store_route_rule_metadata(self, route_rule_metadata):
        for family, rules in route_rule_metadata.items():
            self.raw[family][BaseIface.ROUTE_RULES_METADATA] = rules

    @property
    def copy_mac_from(self):
        return self._info.get(Interface.COPY_MAC_FROM)

    def apply_copy_mac_from(self, mac):
        """
        * Add MAC to original desire.
        * Remove Interface.COPY_MAC_FROM from original desire.
        * Update MAC of merge iface
        """
        self.raw[Interface.MAC] = mac
        self._origin_info[Interface.MAC] = mac
        self._origin_info.pop(Interface.COPY_MAC_FROM, None)

    @property
    def ieee_802_1x_conf(self):
        return self.raw.get(Ieee8021X.CONFIG_SUBTREE, {})


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


def _convert_ovs_external_ids_values_to_string(iface_info):
    external_ids = iface_info.get(OvsDB.OVS_DB_SUBTREE, {}).get(
        OvsDB.EXTERNAL_IDS, {}
    )
    for key, value in external_ids.items():
        external_ids[key] = str(value)
