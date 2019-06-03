#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

from collections import defaultdict
import copy
from operator import itemgetter
import six

from libnmstate import iplib
from libnmstate import metadata
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route


class RouteEntry(object):
    def __init__(self, route):
        self.table_id = route.get(Route.TABLE_ID)
        self.state = route.get(Route.STATE)
        self.metric = route.get(Route.METRIC)
        self.destination = route.get(Route.DESTINATION)
        self.next_hop_address = route.get(Route.NEXT_HOP_ADDRESS)
        self.next_hop_interface = route.get(Route.NEXT_HOP_INTERFACE)
        self.complement_defaults()

    def complement_defaults(self):
        if self.state != Route.STATE_ABSENT:
            if self.table_id is None:
                self.table_id = Route.USE_DEFAULT_ROUTE_TABLE
            if self.metric is None:
                self.metric = Route.USE_DEFAULT_METRIC
            if self.next_hop_address is None:
                self.next_hop_address = ''

    def __hash__(self):
        return hash(self.__keys())

    def __keys(self):
        return (self.table_id, self.metric, self.destination,
                self.next_hop_address, self.next_hop_interface)

    def to_dict(self):
        route_entry = {}
        for key, value in six.viewitems(vars(self)):
            if value is not None:
                route_entry[key.replace('_', '-')] = value
        return route_entry

    def __eq__(self, other):
        return self is other or self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """
        Workaround for python2
        """
        return not self.__eq__(other)

    def is_match(self, other):
        """
        Return True if other route is matched by self absent route.
        """
        if self.state != Route.STATE_ABSENT:
            return False

        if other.state == Route.STATE_ABSENT:
            # Absent route cannot match another absent route
            return False

        for self_value, other_value in zip(self.__keys(), other.__keys()):
            if self_value is not None and self_value != other_value:
                return False
        return True


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


class State(object):
    def __init__(self, state):
        self._state = copy.deepcopy(state)
        self._ifaces_state = State._index_interfaces_state_by_name(self._state)
        self._complement_interface_empty_ip_subtrees()
        self._config_routes = self._state.get(
            Route.KEY, {}).get(Route.CONFIG, [])
        self._config_iface_routes = State._index_routes_by_iface(
            self._config_routes)

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
            list(six.viewvalues(self._ifaces_state)),
            key=itemgetter(Interface.NAME)
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

    def _complement_interface_empty_ip_subtrees(self):
        """ Complement the interfaces states with empty IPv4/IPv6 subtrees. """
        for iface_state in six.viewvalues(self.interfaces):
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
        for ifname, iface_state in six.viewitems(self.interfaces):
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
        for iface_state in six.viewvalues(self.interfaces):
            for family in ('ipv4', 'ipv6'):
                ip = iface_state[family]
                if ip.get('enabled') and (
                        ip.get('dhcp') or ip.get('autoconf')):
                    ip['address'] = []
                else:
                    for dhcp_option in ('auto-routes',
                                        'auto-gateway',
                                        'auto-dns'):
                        ip.pop(dhcp_option, None)

    def verify_interfaces(self, other_state):
        """Verify that the (self) state is a subset of the other_state. """
        self._remove_absent_interfaces()
        self._remove_down_virt_interfaces()

        self._assert_interfaces_included_in(other_state)

        metadata.remove_ifaces_metadata(self)
        other_state.sanitize_dynamic_ip()

        self.merge_interfaces(other_state)

        self.normalize_for_verification()
        other_state.normalize_for_verification()

        self._assert_interfaces_equal(other_state)

    def verify_routes(self, other_state):
        for iface_name, routes in six.viewitems(self.config_iface_routes):
            other_routes = other_state.config_iface_routes.get(iface_name, [])
            if routes != other_routes:
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        {
                            Route.KEY: routes
                        },
                        {
                            Route.KEY: other_routes
                        }))

    def normalize_for_verification(self):
        self._clean_sanitize_ethernet()
        self._sort_lag_slaves()
        self._sort_bridge_ports()
        self._canonicalize_ipv6()
        self._remove_iface_ipv6_link_local_addr()
        self._sort_ip_addresses()
        self._capitalize_mac()

    def merge_interfaces(self, other_state):
        """
        Given the self and other states, complete the self state by merging
        the missing parts from the current state.
        The operation is performed on entries that exist in both states,
        entries that appear only on one state are ignored.
        This is a reverse recursive update operation.
        """
        other_state = State(other_state.state)
        for name in (six.viewkeys(self.interfaces) &
                     six.viewkeys(other_state.interfaces)):
            dict_update(other_state.interfaces[name], self.interfaces[name])
            self._ifaces_state[name] = other_state.interfaces[name]

    def merge_route_config(self, other_state):
        """
        Converting route partial editing to route full editing by
        merging config routes from other state to self.
        Assuming the other state is from `netinfo.show()` which don't have
        absent routes in it.
        """
        iface_enable_states = _get_iface_enable_states(self, other_state)
        ipv4_enable_states = _get_ip_enable_states(
            Interface.IPV4, self, other_state)
        ipv6_enable_states = _get_ip_enable_states(
            Interface.IPV6, self, other_state)
        self_iface_route_sets = defaultdict(set)
        absent_route_sets = set()
        other_iface_route_sets = defaultdict(set)

        for route in self._config_routes:
            if route.get(Route.STATE) == Route.STATE_ABSENT:
                absent_route_sets.add(RouteEntry(route))

        for route in other_state._config_routes:
            # The other_state(running state) does not have any absent
            # route entry and all have NEXT_HOP_INTERFACE
            iface_name = route[Route.NEXT_HOP_INTERFACE]
            other_iface_route_sets[iface_name].add(RouteEntry(route))

        for route in self._config_routes:
            if route.get(Route.STATE) != Route.STATE_ABSENT:
                # The absent route is discarded, so the metadata.py don't need
                # handle it.
                if Route.NEXT_HOP_INTERFACE in route:
                    self_iface_route_sets[route[Route.NEXT_HOP_INTERFACE]].add(
                        RouteEntry(route))

        _validate_routes(self_iface_route_sets,
                         iface_enable_states,
                         ipv4_enable_states,
                         ipv6_enable_states)

        # Absent route can only remove routes in current state.
        _apply_absent_routes(absent_route_sets, other_iface_route_sets)

        for iface_name, route_set in six.viewitems(other_iface_route_sets):
            # The other_state(running state) does not have any absent
            # route entry and all have NEXT_HOP_INTERFACE
            for route_obj in route_set:
                if _route_is_valid(route_obj,
                                   iface_enable_states,
                                   ipv4_enable_states,
                                   ipv6_enable_states):
                    self_iface_route_sets[iface_name].add(route_obj)

        merged_routes = []
        for iface_name, route_set in six.viewitems(self_iface_route_sets):
            merged_routes.extend(
                list(route_obj.to_dict() for route_obj in route_set))

        self._config_routes = merged_routes
        self._config_iface_routes = State._index_routes_by_iface(
            self._config_routes)

    def _remove_absent_interfaces(self):
        ifaces = {}
        for ifname, ifstate in six.viewitems(self.interfaces):
            is_absent = ifstate.get(Interface.STATE) == InterfaceState.ABSENT
            if not is_absent:
                ifaces[ifname] = ifstate
        self._ifaces_state = ifaces

    def _remove_down_virt_interfaces(self):
        ifaces = {}
        for ifname, ifstate in six.viewitems(self.interfaces):
            is_virt_down = (
                ifstate.get(Interface.STATE) == InterfaceState.DOWN and
                ifstate.get(Interface.TYPE) in InterfaceType.VIRT_TYPES
            )
            if not is_virt_down:
                ifaces[ifname] = ifstate
        self._ifaces_state = ifaces

    @staticmethod
    def _index_interfaces_state_by_name(state):
        return {iface[Interface.NAME]: iface
                for iface in state.get(Interface.KEY, [])}

    @staticmethod
    def _index_routes_by_iface(routes):
        iface_routes = defaultdict(list)
        for route in routes:
            iface_name = route.get(Route.NEXT_HOP_INTERFACE)
            if iface_name:
                iface_routes[iface_name].append(route)
        for routes in six.viewvalues(iface_routes):
            routes.sort(key=_route_sort_key)
        return iface_routes

    def _clean_sanitize_ethernet(self):
        for ifstate in six.viewvalues(self.interfaces):
            ethernet_state = ifstate.get(Ethernet.CONFIG_SUBTREE)
            if ethernet_state:
                for key in (Ethernet.AUTO_NEGOTIATION,
                            Ethernet.SPEED,
                            Ethernet.DUPLEX):
                    if ethernet_state.get(key, None) is None:
                        ethernet_state.pop(key, None)
                if not ethernet_state:
                    ifstate.pop(Ethernet.CONFIG_SUBTREE, None)

    def _sort_lag_slaves(self):
        for ifstate in six.viewvalues(self.interfaces):
            ifstate.get('link-aggregation', {}).get('slaves', []).sort()

    def _sort_bridge_ports(self):
        for ifstate in six.viewvalues(self.interfaces):
            ifstate.get('bridge', {}).get('port', []).sort(
                key=itemgetter('name'))

    def _canonicalize_ipv6(self):
        for ifstate in six.viewvalues(self.interfaces):
            new_state = {Interface.IPV6: {'enabled': False, 'address': []}}
            dict_update(new_state, ifstate)
            self._ifaces_state[ifstate[Interface.NAME]] = new_state

    def _remove_iface_ipv6_link_local_addr(self):
        for ifstate in six.viewvalues(self.interfaces):
            ifstate['ipv6']['address'] = list(
                addr for addr in ifstate['ipv6']['address']
                if not iplib.is_ipv6_link_local_addr(addr['ip'],
                                                     addr['prefix-length'])
            )

    def _sort_ip_addresses(self):
        for ifstate in six.viewvalues(self.interfaces):
            for family in ('ipv4', 'ipv6'):
                ifstate[family].get('address', []).sort(key=itemgetter('ip'))

    def _capitalize_mac(self):
        for ifstate in six.viewvalues(self.interfaces):
            mac = ifstate.get(Interface.MAC)
            if mac:
                ifstate[Interface.MAC] = mac.upper()

    def _assert_interfaces_equal(self, current_state):
        for ifname in self.interfaces:
            iface_dstate = self.interfaces[ifname]
            iface_cstate = current_state.interfaces[ifname]

            if iface_dstate != iface_cstate:
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        self.interfaces[ifname],
                        current_state.interfaces[ifname]
                    )
                )

    def _assert_interfaces_included_in(self, current_state):
        if not (set(self.interfaces) <= set(
                current_state.interfaces)):
            raise NmstateVerificationError(
                format_desired_current_state_diff(self.interfaces,
                                                  current_state.interfaces))


def dict_update(origin_data, to_merge_data):
    """Recursevely performes a dict update (merge)"""

    for key, val in six.viewitems(to_merge_data):
        if isinstance(val, Mapping):
            origin_data[key] = dict_update(origin_data.get(key, {}), val)
        else:
            origin_data[key] = val
    return origin_data


def _route_sort_key(route):
    return (route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
            route.get(Route.NEXT_HOP_INTERFACE, ''),
            route.get(Route.DESTINATION, ''))


def _validate_routes(iface_route_sets, iface_enable_states,
                     ipv4_enable_states, ipv6_enable_states):
    """
    Check whether user desire routes next hop to:
        * down/absent interface
        * Non-exit interface
        * IPv4/IPv6 disabled
    """
    for iface_name, route_set in six.viewitems(iface_route_sets):
        if not route_set:
            continue
        iface_enable_state = iface_enable_states.get(iface_name)
        if iface_enable_state is None:
            raise NmstateValueError('Cannot set route to non-exist interface')
        if iface_enable_state != InterfaceState.UP:
            raise NmstateValueError(
                'Cannot set route to {} interface'.format(iface_enable_state))
        # Interface is already check, so the ip enable status should be defined
        ipv4_enabled = ipv4_enable_states[iface_name]
        ipv6_enabled = ipv6_enable_states[iface_name]
        for route_obj in route_set:
            if iplib.is_ipv6_address(route_obj.destination):
                if not ipv6_enabled:
                    raise NmstateValueError(
                        'Cannot set IPv6 route when IPv6 is disabled')
            elif not ipv4_enabled:
                    raise NmstateValueError(
                        'Cannot set IPv4 route when IPv4 is disabled')


def _get_iface_enable_states(desire_state, current_state):
    iface_enable_states = {}
    for iface_name, iface_state in six.viewitems(current_state.interfaces):
        iface_enable_states[iface_name] = iface_state[Interface.STATE]
    for iface_name, iface_state in six.viewitems(desire_state.interfaces):
        if Interface.STATE in iface_state:
            # If desire_state does not have Interface.STATE, it will use
            # current_state settings.
            iface_enable_states[iface_name] = iface_state[Interface.STATE]
    return iface_enable_states


def _get_ip_enable_states(family, desire_state, current_state):
    ip_enable_states = {}
    for iface_name, iface_state in six.viewitems(current_state.interfaces):
        ip_enable_states[iface_name] = iface_state.get(
            family, {}).get('enabled', False)
    for iface_name, iface_state in six.viewitems(desire_state.interfaces):
        ip_enable_state = iface_state.get(family, {}).get('enabled')
        if ip_enable_state is not None:
            # If desire_state does not have Interface.IPV4/IPV6, it will use
            # current_state settings.
            ip_enable_states[iface_name] = ip_enable_state

    return ip_enable_states


def _route_is_valid(route_obj, iface_enable_states, ipv4_enable_states,
                    ipv6_enable_states):
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
        for iface_name, route_set in six.viewitems(iface_route_sets):
            if absent_iface_name and absent_iface_name != iface_name:
                continue
            new_routes = set()
            for route in route_set:
                if not absent_route.is_match(route):
                    new_routes.add(route)
            iface_route_sets[iface_name] = new_routes
