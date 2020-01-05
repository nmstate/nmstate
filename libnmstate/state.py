#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

try:
    from collections.abc import Mapping
    from collections.abc import Sequence
except ImportError:
    from collections import Mapping
    from collections import Sequence

from abc import ABCMeta
from abc import abstractmethod
from collections import defaultdict
import copy
from functools import total_ordering
from ipaddress import ip_address
from operator import itemgetter

from libnmstate import iplib
from libnmstate import metadata
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.iplib import is_ipv6_address
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import DNS
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge
from libnmstate.schema import Route
from libnmstate.schema import RouteRule


NON_UP_STATES = (InterfaceState.DOWN, InterfaceState.ABSENT)


@total_ordering
class StateEntry(metaclass=ABCMeta):
    @abstractmethod
    def _keys(self):
        """
        Return the tuple representing this entry, will be used for hashing or
        comparing.
        """
        pass

    def __hash__(self):
        return hash(self._keys())

    def __eq__(self, other):
        return self is other or self._keys() == other._keys()

    def __lt__(self, other):
        return self._keys() < other._keys()

    def __repr__(self):
        return str(self.to_dict())

    @property
    @abstractmethod
    def absent(self):
        pass

    def to_dict(self):
        return {
            key.replace("_", "-"): value
            for key, value in vars(self).items()
            if (not key.startswith("_")) and (value is not None)
        }

    def match(self, other):
        """
        Match self against other. Treat self None attributes as wildcards,
        matching against any value in others.
        Return True for a match, False otherwise.
        """
        for self_value, other_value in zip(self._keys(), other._keys()):
            if self_value is not None and self_value != other_value:
                return False
        return True


class RouteEntry(StateEntry):
    def __init__(self, route):
        self.table_id = route.get(Route.TABLE_ID)
        self.state = route.get(Route.STATE)
        self.metric = route.get(Route.METRIC)
        self.destination = route.get(Route.DESTINATION)
        self.next_hop_address = route.get(Route.NEXT_HOP_ADDRESS)
        self.next_hop_interface = route.get(Route.NEXT_HOP_INTERFACE)
        self.complement_defaults()

    def complement_defaults(self):
        if not self.absent:
            if self.table_id is None:
                self.table_id = Route.USE_DEFAULT_ROUTE_TABLE
            if self.metric is None:
                self.metric = Route.USE_DEFAULT_METRIC
            if self.next_hop_address is None:
                self.next_hop_address = ""

    def _keys(self):
        return (
            self.table_id,
            self.metric,
            self.destination,
            self.next_hop_address,
            self.next_hop_interface,
        )

    def __lt__(self, other):
        return (
            self.table_id or Route.USE_DEFAULT_ROUTE_TABLE,
            self.next_hop_interface or "",
            self.destination or "",
        ) < (
            other.table_id or Route.USE_DEFAULT_ROUTE_TABLE,
            other.next_hop_interface or "",
            other.destination or "",
        )

    @property
    def absent(self):
        return self.state == Route.STATE_ABSENT


class RouteRuleEntry(StateEntry):
    def __init__(self, route_rule):
        self.ip_from = route_rule.get(RouteRule.IP_FROM)
        self.ip_to = route_rule.get(RouteRule.IP_TO)
        self.priority = route_rule.get(RouteRule.PRIORITY)
        self.route_table = route_rule.get(RouteRule.ROUTE_TABLE)
        self.complement_defaults()

    def complement_defaults(self):
        if self.ip_from is None:
            self.ip_from = ""
        if self.ip_to is None:
            self.ip_to = ""
        if self.priority is None:
            self.priority = RouteRule.USE_DEFAULT_PRIORITY
        if (
            self.route_table is None
            or self.route_table == RouteRule.USE_DEFAULT_ROUTE_TABLE
        ):
            self.route_table = iplib.KERNEL_MAIN_ROUTE_TABLE_ID

    def _keys(self):
        return (self.ip_from, self.ip_to, self.priority, self.route_table)

    @property
    def absent(self):
        raise NmstateNotImplementedError(
            "RouteRuleEntry does not support absent property"
        )


def create_state(state, interfaces_to_filter=None):
    """
    Create a state object, given an initial state.
    interface_filter: Limit the interfaces included in the state to the ones
    mentioned in the list. None implied no filtering.
    """
    new_state = {}
    if interfaces_to_filter is not None:
        origin = State(state)
        iface_names = set(origin.interfaces) & interfaces_to_filter
        filtered_ifaces_state = [
            origin.interfaces[ifname] for ifname in iface_names
        ]
        new_state[Interface.KEY] = filtered_ifaces_state

    return State(new_state)


class State:
    def __init__(self, state):
        self._state = copy.deepcopy(state)

        self._ifaces_state = self._index_interfaces_state_by_name()
        self._complement_interface_empty_ip_subtrees()

        self._config_iface_routes = self._index_routes_by_iface()

        (
            self._config_route_table_rules_v4,
            self._config_route_table_rules_v6,
        ) = self._index_route_rule_by_route_table()

    def __eq__(self, other):
        return self.state == other.state

    def __hash__(self):
        return hash(self.state)

    def __str__(self):
        return str(self.state)

    def __repr__(self):
        return self.__str__()

    @property
    def state(self):
        self._state[Interface.KEY] = sorted(
            list(self._ifaces_state.values()), key=itemgetter(Interface.NAME)
        )
        return self._state

    @property
    def interfaces(self):
        """ Indexed interfaces state """
        return self._ifaces_state

    @property
    def config_iface_routes(self):
        """
        Indexed config routes by next hop interface name. Read only.
        """
        return self._config_iface_routes

    @property
    def config_dns(self):
        dns_conf = self._state.get(DNS.KEY, {}).get(DNS.CONFIG, {})
        return {
            DNS.SERVER: dns_conf.get(DNS.SERVER, []),
            DNS.SEARCH: dns_conf.get(DNS.SEARCH, []),
        }

    @property
    def config_route_table_rules_v4(self):
        """
        IPv4 Route rules indexed by route table number.
        """
        return self._config_route_table_rules_v4

    @property
    def config_route_table_rules_v6(self):
        """
        IPv6 Route rules indexed by route table number.
        """
        return self._config_route_table_rules_v6

    def _complement_interface_empty_ip_subtrees(self):
        """ Complement the interfaces states with empty IPv4/IPv6 subtrees. """
        for iface_state in self.interfaces.values():
            for family in (Interface.IPV4, Interface.IPV6):
                if family not in iface_state:
                    iface_state[family] = {}

    def sanitize_ethernet(self, other_state):
        """
        Given the other_state, update the ethernet interfaces state base on
        the other_state ethernet interfaces data.
        Usually the other_state represents the current state.
        If auto-negotiation, speed and duplex settings are not provided,
        but exist in the current state, they need to be set to None
        to not override them with the values from the current settings
        since the current settings are read from the device state and not
        from the actual configuration.  This makes it possible to distinguish
        whether a user specified these values in the later configuration step.
        """
        for ifname, iface_state in self.interfaces.items():
            iface_current_state = other_state.interfaces.get(ifname, {})
            if iface_current_state.get(Interface.TYPE) == Ethernet.TYPE:
                ethernet = iface_state.setdefault(Ethernet.CONFIG_SUBTREE, {})
                ethernet.setdefault(Ethernet.AUTO_NEGOTIATION, None)
                ethernet.setdefault(Ethernet.SPEED, None)
                ethernet.setdefault(Ethernet.DUPLEX, None)

    def sanitize_dynamic_ip(self):
        """
        If dynamic IP is enabled and IP address is missing, set an empty
        address list. This assures that the desired state is not complemented
        by the current state address values.
        If dynamic IP is disabled, all dynamic IP options should be removed.
        """
        for iface_state in self.interfaces.values():
            for family in ("ipv4", "ipv6"):
                ip = iface_state[family]
                if ip.get(InterfaceIP.ENABLED) and (
                    ip.get(InterfaceIP.DHCP) or ip.get(InterfaceIPv6.AUTOCONF)
                ):
                    ip[InterfaceIP.ADDRESS] = []
                else:
                    for dhcp_option in (
                        InterfaceIP.AUTO_ROUTES,
                        InterfaceIP.AUTO_GATEWAY,
                        InterfaceIP.AUTO_DNS,
                    ):
                        ip.pop(dhcp_option, None)

    def verify_interfaces(self, other_state):
        """Verify that the (self) state is a subset of the other_state. """
        self._remove_absent_interfaces()
        self._remove_down_virt_interfaces()
        other_state.remove_unmanaged_bridge_ports()

        self._assert_interfaces_included_in(other_state)

        metadata.remove_ifaces_metadata(self)
        other_state.sanitize_dynamic_ip()

        self.merge_interfaces(other_state)

        self.normalize_for_verification()
        other_state.normalize_for_verification()

        self._assert_interfaces_equal(other_state)

    def verify_routes(self, other_state):
        for iface_name, routes in self.config_iface_routes.items():
            other_routes = other_state.config_iface_routes.get(iface_name, [])
            if routes != other_routes:
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        {Route.KEY: [r.to_dict() for r in routes]},
                        {Route.KEY: [r.to_dict() for r in other_routes]},
                    )
                )

    def verify_dns(self, other_state):
        if self.config_dns != other_state.config_dns:
            raise NmstateVerificationError(
                format_desired_current_state_diff(
                    {DNS.KEY: self.config_dns},
                    {DNS.KEY: other_state.config_dns},
                )
            )

    def verify_route_rule(self, other_state):
        _verify_route_rules(
            self.config_route_table_rules_v4,
            other_state.config_route_table_rules_v4,
        )
        _verify_route_rules(
            self.config_route_table_rules_v6,
            other_state.config_route_table_rules_v6,
        )

    def normalize_for_verification(self):
        self._clean_sanitize_ethernet()
        self._sort_lag_slaves()
        self._sort_bridge_ports()
        self._canonicalize_ipv6()
        self._remove_iface_ipv6_link_local_addr()
        self._sort_ip_addresses()
        self._capitalize_mac()
        self._remove_empty_description()
        self._remove_ip_stack_if_disabled()

    def merge_interfaces(self, other_state):
        """
        Given the self and other states, complete the self state by merging
        the missing parts from the current state.
        The operation is performed on entries that exist in both states,
        entries that appear only on one state are ignored.
        This is a reverse recursive update operation.
        """
        other_state = State(other_state.state)
        for name in self.interfaces.keys() & other_state.interfaces.keys():
            dict_update(other_state.interfaces[name], self.interfaces[name])
            self._ifaces_state[name] = other_state.interfaces[name]

    def remove_unknown_interfaces(self):
        """
        Remove unknown type interfaces
        """
        unknown_ifaces = [
            ifname
            for ifname, ifstate in self.interfaces.items()
            if ifstate.get(Interface.TYPE) == InterfaceType.UNKNOWN
        ]
        for unknown_iface in unknown_ifaces:
            del self.interfaces[unknown_iface]

    def merge_routes(self, other_state):
        """
        Given the self and other states, complete the self state by merging
        the routes form the current state.
        The resulting routes are a combination of the current routes and the
        desired routes:
        - Self routes are kept.
        - Other routes are kept if:
          - There are self routes under iface OR
          - Self iface explicitly specified (regardless of routes)
        - Self absent routes overwrite other routes state.
          - Support wildcard for matching the absent routes.
        """
        other_routes = set()
        for ifname, routes in other_state.config_iface_routes.items():
            if (
                ifname in self.config_iface_routes
                or self._is_interface_routable(ifname, routes)
            ):
                other_routes |= set(routes)

        self_routes = {
            route
            for routes in self.config_iface_routes.values()
            for route in routes
            if not route.absent
        }

        absent_routes = set()
        for routes in self.config_iface_routes.values():
            for absent_route in (r for r in routes if r.absent):
                absent_routes |= {
                    r for r in other_routes if absent_route.match(r)
                }

        merged_routes = (other_routes | self_routes) - absent_routes
        self._config_routes = [r.to_dict() for r in sorted(merged_routes)]
        # FIXME: Index based on route objects directly.
        self._config_iface_routes = self._index_routes_by_iface()

    def _is_interface_routable(self, ifname, routes):
        """
        And interface is able to support routes if:
        - It exists.
        - It is not DOWN or ABSENT.
        - It is not IPv4/6 disabled (corresponding to the routes).
        """
        ifstate = self.interfaces.get(ifname)
        if not ifstate:
            return False

        iface_up = ifstate.get(Interface.STATE) not in NON_UP_STATES
        if iface_up:
            ipv4_state = ifstate.get(Interface.IPV4, {})
            ipv4_disabled = ipv4_state.get(InterfaceIPv4.ENABLED) is False
            if ipv4_disabled and any(
                not is_ipv6_address(r.destination) for r in routes
            ):
                return False

            ipv6_state = ifstate.get(Interface.IPV6, {})
            ipv6_disabled = ipv6_state.get(InterfaceIPv6.ENABLED) is False
            if ipv6_disabled and any(
                is_ipv6_address(r.destination) for r in routes
            ):
                return False

            return True

        return False

    def merge_dns(self, other_state):
        """
        If DNS is not mentioned in the self state, overwrite it with the other
        DNS entries.
        """
        if not self._state.get(DNS.KEY):
            self._state[DNS.KEY] = {
                DNS.CONFIG: copy.deepcopy(other_state.config_dns)
            }

    def _remove_absent_interfaces(self):
        ifaces = {}
        for ifname, ifstate in self.interfaces.items():
            is_absent = ifstate.get(Interface.STATE) == InterfaceState.ABSENT
            if not is_absent:
                ifaces[ifname] = ifstate
        self._ifaces_state = ifaces

    def _remove_down_virt_interfaces(self):
        ifaces = {}
        for ifname, ifstate in self.interfaces.items():
            is_virt_down = (
                ifstate.get(Interface.STATE) == InterfaceState.DOWN
                and ifstate.get(Interface.TYPE) in InterfaceType.VIRT_TYPES
            )
            if not is_virt_down:
                ifaces[ifname] = ifstate
        self._ifaces_state = ifaces

    def remove_unmanaged_bridge_ports(self):
        """
        Remove ports which should not be managed/controlled.
        """
        ports2remove = set()
        bridge_ifaces = (
            ifstate
            for ifstate in self.interfaces.values()
            if ifstate[Interface.STATE] == InterfaceState.UP
            and ifstate[Interface.TYPE]
            in (InterfaceType.LINUX_BRIDGE, InterfaceType.OVS_BRIDGE)
        )
        for br_ifstate in bridge_ifaces:
            bridge_state = br_ifstate[LinuxBridge.CONFIG_SUBTREE]
            ports_by_name = {
                port[LinuxBridge.Port.NAME]: port
                for port in bridge_state.get(LinuxBridge.PORT_SUBTREE, [])
            }
            for port in ports_by_name:
                port_ifstate = self.interfaces.get(port)
                if port_ifstate:
                    if (
                        port_ifstate.get(Interface.STATE) != InterfaceState.UP
                        or port_ifstate.get(Interface.TYPE)
                        == InterfaceType.UNKNOWN
                    ):
                        ports2remove.add(port_ifstate[Interface.NAME])
            if ports_by_name:
                new_ports_states = [
                    ports_by_name[port_name]
                    for port_name in (set(ports_by_name) - ports2remove)
                ]
                bridge_state[LinuxBridge.PORT_SUBTREE] = new_ports_states

    def _index_interfaces_state_by_name(self):
        return {
            iface[Interface.NAME]: iface
            for iface in self._state.get(Interface.KEY, [])
        }

    def _index_routes_by_iface(self):
        iface_routes = defaultdict(list)
        for route in self._config_routes:
            iface_name = route.get(Route.NEXT_HOP_INTERFACE, "")
            iface_routes[iface_name].append(RouteEntry(route))
        for routes in iface_routes.values():
            routes.sort()
        return iface_routes

    def _index_route_rule_by_route_table(self):
        index_rules_v4 = defaultdict(list)
        index_rules_v6 = defaultdict(list)
        for rule in self._config_route_rules:
            entry = RouteRuleEntry(rule)
            if is_ipv6_address(entry.ip_from) or is_ipv6_address(entry.ip_to):
                index_rules_v6[entry.route_table].append(entry)
            else:
                index_rules_v4[entry.route_table].append(entry)
        for rules in index_rules_v4.values():
            rules.sort()
        for rules in index_rules_v6.values():
            rules.sort()
        return index_rules_v4, index_rules_v6

    def _clean_sanitize_ethernet(self):
        for ifstate in self.interfaces.values():
            ethernet_state = ifstate.get(Ethernet.CONFIG_SUBTREE)
            if ethernet_state:
                for key in (
                    Ethernet.AUTO_NEGOTIATION,
                    Ethernet.SPEED,
                    Ethernet.DUPLEX,
                ):
                    if ethernet_state.get(key, None) is None:
                        ethernet_state.pop(key, None)
                if not ethernet_state:
                    ifstate.pop(Ethernet.CONFIG_SUBTREE, None)

    def _sort_lag_slaves(self):
        for ifstate in self.interfaces.values():
            ifstate.get("link-aggregation", {}).get("slaves", []).sort()

    def _sort_bridge_ports(self):
        for ifstate in self.interfaces.values():
            ifstate.get("bridge", {}).get("port", []).sort(
                key=itemgetter("name")
            )

    def _canonicalize_ipv6(self):
        for ifstate in self.interfaces.values():
            new_state = {
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: False,
                    InterfaceIPv6.ADDRESS: [],
                }
            }
            dict_update(new_state, ifstate)
            ipv6_addrs = new_state[Interface.IPV6].get(
                InterfaceIPv6.ADDRESS, []
            )
            if ipv6_addrs:
                compressed_addresses = [
                    canonicalize_ipv6_addr(ipv6_addr)
                    for ipv6_addr in ipv6_addrs
                ]
                new_state[Interface.IPV6][
                    InterfaceIPv6.ADDRESS
                ] = compressed_addresses
            self._ifaces_state[ifstate[Interface.NAME]] = new_state

    def _remove_iface_ipv6_link_local_addr(self):
        for ifstate in self.interfaces.values():
            ifstate["ipv6"][InterfaceIPv6.ADDRESS] = list(
                addr
                for addr in ifstate["ipv6"][InterfaceIPv6.ADDRESS]
                if not iplib.is_ipv6_link_local_addr(
                    addr[InterfaceIPv6.ADDRESS_IP],
                    addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
                )
            )

    def _remove_ip_stack_if_disabled(self):
        for ifstate in self.interfaces.values():
            for family in (Interface.IPV4, Interface.IPV6):
                ip_state = ifstate.get(family)
                if ip_state and not ip_state.get(InterfaceIP.ENABLED):
                    ifstate[family] = {InterfaceIP.ENABLED: False}

    def _sort_ip_addresses(self):
        for ifstate in self.interfaces.values():
            for family in ("ipv4", "ipv6"):
                ifstate[family].get(InterfaceIP.ADDRESS, []).sort(
                    key=itemgetter(InterfaceIP.ADDRESS_IP)
                )

    def _capitalize_mac(self):
        for ifstate in self.interfaces.values():
            mac = ifstate.get(Interface.MAC)
            if mac:
                ifstate[Interface.MAC] = mac.upper()

    def _remove_empty_description(self):
        for ifstate in self.interfaces.values():
            if ifstate.get(Interface.DESCRIPTION) == "":
                del ifstate[Interface.DESCRIPTION]

    def _assert_interfaces_equal(self, current_state):
        for ifname in self.interfaces:
            iface_dstate = self.interfaces[ifname]
            iface_cstate = current_state.interfaces[ifname]
            if not state_match(iface_dstate, iface_cstate):
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        self.interfaces[ifname],
                        current_state.interfaces[ifname],
                    )
                )

    def _assert_interfaces_included_in(self, current_state):
        if not (set(self.interfaces) <= set(current_state.interfaces)):
            raise NmstateVerificationError(
                format_desired_current_state_diff(
                    self.interfaces, current_state.interfaces
                )
            )

    @property
    def _config_routes(self):
        return self._state.get(Route.KEY, {}).get(Route.CONFIG, [])

    @_config_routes.setter
    def _config_routes(self, value):
        routes = self._state.get(Route.KEY)
        if not routes:
            routes = self._state[Route.KEY] = {}
        routes[Route.CONFIG] = value

    @property
    def _config_route_rules(self):
        return self._state.get(RouteRule.KEY, {}).get(RouteRule.CONFIG, [])

    def merge_route_rules(self, other_state):
        if not self._state.get(RouteRule.KEY):
            self._state[RouteRule.KEY] = {
                RouteRule.CONFIG: copy.deepcopy(
                    other_state._config_route_rules
                )
            }


def dict_update(origin_data, to_merge_data):
    """Recursevely performes a dict update (merge)"""

    for key, val in to_merge_data.items():
        if isinstance(val, Mapping):
            origin_data[key] = dict_update(origin_data.get(key, {}), val)
        else:
            origin_data[key] = val
    return origin_data


def _validate_routes(
    iface_route_sets,
    iface_enable_states,
    ipv4_enable_states,
    ipv6_enable_states,
):
    """
    Check whether user desire routes next hop to:
        * down/absent interface
        * Non-exit interface
        * IPv4/IPv6 disabled
    """
    for iface_name, route_set in iface_route_sets.items():
        if not route_set:
            continue
        iface_enable_state = iface_enable_states.get(iface_name)
        if iface_enable_state is None:
            raise NmstateValueError("Cannot set route to non-exist interface")
        if iface_enable_state != InterfaceState.UP:
            raise NmstateValueError(
                "Cannot set route to {} interface".format(iface_enable_state)
            )
        # Interface is already check, so the ip enable status should be defined
        ipv4_enabled = ipv4_enable_states[iface_name]
        ipv6_enabled = ipv6_enable_states[iface_name]
        for route_obj in route_set:
            if iplib.is_ipv6_address(route_obj.destination):
                if not ipv6_enabled:
                    raise NmstateValueError(
                        "Cannot set IPv6 route when IPv6 is disabled"
                    )
            elif not ipv4_enabled:
                raise NmstateValueError(
                    "Cannot set IPv4 route when IPv4 is disabled"
                )


def canonicalize_ipv6_addr(ipv6_address_prefix_len):
    ipv6_address = ipv6_address_prefix_len[InterfaceIPv6.ADDRESS_IP]
    ipv6_iface = ip_address(ipv6_address)

    return {
        InterfaceIPv6.ADDRESS_IP: str(ipv6_iface),
        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: ipv6_address_prefix_len[
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH
        ],
    }


def _get_iface_enable_states(desire_state, current_state):
    iface_enable_states = {}
    for iface_name, iface_state in current_state.interfaces.items():
        iface_enable_states[iface_name] = iface_state[Interface.STATE]
    for iface_name, iface_state in desire_state.interfaces.items():
        if Interface.STATE in iface_state:
            # If desire_state does not have Interface.STATE, it will use
            # current_state settings.
            iface_enable_states[iface_name] = iface_state[Interface.STATE]
    return iface_enable_states


def _get_ip_enable_states(family, desire_state, current_state):
    ip_enable_states = {}
    for iface_name, iface_state in current_state.interfaces.items():
        ip_enable_states[iface_name] = iface_state.get(family, {}).get(
            InterfaceIP.ENABLED, False
        )
    for iface_name, iface_state in desire_state.interfaces.items():
        ip_enable_state = iface_state.get(family, {}).get(InterfaceIP.ENABLED)
        if ip_enable_state is not None:
            # If desire_state does not have Interface.IPV4/IPV6, it will use
            # current_state settings.
            ip_enable_states[iface_name] = ip_enable_state

    return ip_enable_states


def _route_is_valid(
    route_obj, iface_enable_states, ipv4_enable_states, ipv6_enable_states
):
    """
    Return False when route is next hop to any of these interfaces:
        * Interface not in InterfaceState.UP state.
        * Interface does not exists.
        * Interface has IPv4/IPv6 disabled.
    """
    iface_name = route_obj.next_hop_interface
    iface_enable_state = iface_enable_states.get(iface_name)
    if iface_enable_state != InterfaceState.UP:
        return False
    if iplib.is_ipv6_address(route_obj.destination):
        if not ipv6_enable_states.get(iface_name):
            return False
    else:
        if not ipv4_enable_states.get(iface_name):
            return False
    return True


def _apply_absent_routes(absent_route_sets, iface_route_sets):
    """
    Remove routes based on absent routes and treat missing property as wildcard
    match.
    """
    for absent_route in absent_route_sets:
        absent_iface_name = absent_route.next_hop_interface
        for iface_name, route_set in iface_route_sets.items():
            if absent_iface_name and absent_iface_name != iface_name:
                continue
            new_routes = set()
            for route in route_set:
                if not absent_route.match(route):
                    new_routes.add(route)
            iface_route_sets[iface_name] = new_routes


def state_match(desire, current):
    """
    Return True when all values defined in desire equal to value in current,
    else False.
    """
    if isinstance(desire, Mapping):
        return isinstance(current, Mapping) and all(
            state_match(val, current.get(key)) for key, val in desire.items()
        )
    elif isinstance(desire, Sequence) and not isinstance(desire, str):
        return (
            isinstance(current, Sequence)
            and not isinstance(current, str)
            and len(current) == len(desire)
            and all(state_match(d, c) for d, c in zip(desire, current))
        )
    else:
        return desire == current


def _verify_route_rules(self_indexed_rules, other_indexed_rules):
    for table_id, rules in self_indexed_rules.items():
        self_rules = [
            _remove_route_rule_default_values(rule.to_dict()) for rule in rules
        ]
        other_rules = [
            rule.to_dict() for rule in other_indexed_rules.get(table_id, [])
        ]
        if not state_match(self_rules, other_rules):
            raise NmstateVerificationError(
                format_desired_current_state_diff(
                    {RouteRule.KEY: {RouteRule.CONFIG: self_rules}},
                    {RouteRule.KEY: {RouteRule.CONFIG: other_rules}},
                )
            )


def _remove_route_rule_default_values(rule):
    if rule.get(RouteRule.PRIORITY) == RouteRule.USE_DEFAULT_PRIORITY:
        del rule[RouteRule.PRIORITY]
    if rule.get(RouteRule.ROUTE_TABLE) == RouteRule.USE_DEFAULT_ROUTE_TABLE:
        del rule[RouteRule.ROUTE_TABLE]
    return rule
