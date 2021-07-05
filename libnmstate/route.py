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

from collections import defaultdict
import logging

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.iplib import is_ipv6_address
from libnmstate.iplib import canonicalize_ip_network
from libnmstate.iplib import canonicalize_ip_address
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_string

from .ifaces.base_iface import BaseIface
from .state import StateEntry


DEFAULT_ROUTE_TABLE = 254


ROUTE_REMOVED = "_route_removed"


class RouteEntry(StateEntry):
    IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
    IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"

    def __init__(self, route):
        self.table_id = route.get(Route.TABLE_ID)
        self.state = route.get(Route.STATE)
        self.metric = route.get(Route.METRIC)
        self.destination = route.get(Route.DESTINATION)
        self.next_hop_address = route.get(Route.NEXT_HOP_ADDRESS)
        self.next_hop_interface = route.get(Route.NEXT_HOP_INTERFACE)
        # TODO: Convert IPv6 full address to abbreviated address
        self.complement_defaults()
        self._invalid_reason = None
        self._canonicalize_ip_address()

    @property
    def is_ipv6(self):
        return is_ipv6_address(self.destination)

    @property
    def is_gateway(self):
        if self.is_ipv6:
            return (
                self.destination == RouteEntry.IPV6_DEFAULT_GATEWAY_DESTINATION
            )
        else:
            return (
                self.destination == RouteEntry.IPV4_DEFAULT_GATEWAY_DESTINATION
            )

    @property
    def invalid_reason(self):
        return self._invalid_reason

    def validate_properties(self):
        validate_string(self.state, Route.STATE, [Route.STATE_ABSENT])
        validate_integer(self.table_id, Route.TABLE_ID)
        validate_integer(self.metric, Route.METRIC)
        validate_string(self.destination, Route.DESTINATION)
        validate_string(self.next_hop_interface, Route.NEXT_HOP_INTERFACE)
        validate_string(self.next_hop_address, Route.NEXT_HOP_ADDRESS)

    def complement_defaults(self):
        if self.absent:
            if self.table_id == Route.USE_DEFAULT_ROUTE_TABLE:
                self.table_id = DEFAULT_ROUTE_TABLE
            if self.metric == Route.USE_DEFAULT_METRIC:
                self.metric = None
        else:
            if (
                self.table_id is None
                or self.table_id == Route.USE_DEFAULT_ROUTE_TABLE
            ):
                self.table_id = DEFAULT_ROUTE_TABLE
            if self.metric is None:
                self.metric = Route.USE_DEFAULT_METRIC
            if self.next_hop_address is None:
                self.next_hop_address = ""

    def _keys(self):
        return (
            self.table_id,
            self.destination,
            self.next_hop_address,
            self.next_hop_interface,
        )

    def __lt__(self, other):
        return (
            self.table_id or Route.USE_DEFAULT_ROUTE_TABLE,
            self.next_hop_interface or "",
            self.destination or "",
            self.next_hop_address or "",
            self.metric or Route.USE_DEFAULT_METRIC,
        ) < (
            other.table_id or Route.USE_DEFAULT_ROUTE_TABLE,
            other.next_hop_interface or "",
            other.destination or "",
            other.next_hop_address or "",
            other.metric or Route.USE_DEFAULT_METRIC,
        )

    @property
    def absent(self):
        return self.state == Route.STATE_ABSENT

    def is_valid(self, ifaces):
        """
        Return False when next hop interface or destination not defined;
        Return False when route is next hop to any of these interfaces:
            * Interface not in InterfaceState.UP state.
            * Interface does not exists.
            * Interface has IPv4/IPv6 disabled.
            * Interface configured as dynamic IPv4/IPv6.
        """
        if not self.next_hop_interface:
            self._invalid_reason = (
                "Route entry does not have next hop interface"
            )
            return False
        if not self.destination:
            self._invalid_reason = "Route entry does not have destination"
            return False
        iface = ifaces.all_kernel_ifaces.get(self.next_hop_interface)
        if not iface:
            self._invalid_reason = (
                f"Route {self.to_dict()} next hop to unknown interface"
            )
            return False
        if not iface.is_up:
            self._invalid_reason = (
                f"Route {self.to_dict()} next hop to down/absent interface"
            )
            return False
        if iface.is_dynamic(
            Interface.IPV6 if self.is_ipv6 else Interface.IPV4
        ):
            self._invalid_reason = (
                f"Route {self.to_dict()} next hop to interface with dynamic IP"
            )
            return False
        if self.is_ipv6:
            if not iface.is_ipv6_enabled():
                self._invalid_reason = (
                    f"Route {self.to_dict()} next hop to interface with IPv6 "
                    "disabled"
                )
                return False
        else:
            if not iface.is_ipv4_enabled():
                self._invalid_reason = (
                    f"Route {self.to_dict()} next hop to interface with IPv4 "
                    "disabled"
                )
                return False
        return True

    def _canonicalize_ip_address(self):
        if not self.absent:
            if self.destination:
                self.destination = canonicalize_ip_network(self.destination)
            if self.next_hop_address:
                self.next_hop_address = canonicalize_ip_address(
                    self.next_hop_address
                )

    def to_dict(self):
        info = super().to_dict()
        if self.metric == Route.USE_DEFAULT_METRIC:
            del info[Route.METRIC]
        return info


class RouteState:
    def __init__(self, ifaces, des_route_state, cur_route_state):
        self._cur_routes = defaultdict(set)
        self._routes = defaultdict(set)
        if cur_route_state:
            for entry in cur_route_state.get(Route.CONFIG, []):
                rt = RouteEntry(entry)
                self._cur_routes[rt.next_hop_interface].add(rt)
                if not ifaces or rt.is_valid(ifaces):
                    self._routes[rt.next_hop_interface].add(rt)
                else:
                    logging.debug(
                        f"The current route {entry} has been discarded due"
                        f" to {rt.invalid_reason}"
                    )
        if des_route_state:
            self._merge_routes(des_route_state, ifaces)

    def _merge_routes(self, des_route_state, ifaces):
        # Handle absent route before adding desired route entries to
        # make sure absent route does not delete route defined in
        # desire state
        for entry in des_route_state.get(Route.CONFIG, []):
            rt = RouteEntry(entry)
            rt.validate_properties()
            if rt.absent:
                self._apply_absent_routes(rt, ifaces)
        for entry in des_route_state.get(Route.CONFIG, []):
            rt = RouteEntry(entry)
            if not rt.absent:
                if rt.is_valid(ifaces):
                    ifaces.all_kernel_ifaces[
                        rt.next_hop_interface
                    ].mark_as_changed()
                    self._routes[rt.next_hop_interface].add(rt)
                else:
                    raise NmstateValueError(rt.invalid_reason)

    def _apply_absent_routes(self, rt, ifaces):
        """
        Remove routes based on absent routes and treat missing property as
        wildcard match.
        """
        absent_iface_name = rt.next_hop_interface
        for iface_name, route_set in self._routes.items():
            if absent_iface_name and absent_iface_name != iface_name:
                continue
            new_routes = set()
            for route in route_set:
                if not rt.match(route):
                    new_routes.add(route)
                # The routes match and therefore it is being removed.
                # marking the interface as deactivate first.
                #
                # This is a workaround for NM bug:
                # https://bugzilla.redhat.com/1837254
                # https://bugzilla.redhat.com/1962551
                ifaces.all_kernel_ifaces[iface_name].raw[ROUTE_REMOVED] = True
            if new_routes != route_set:
                self._routes[iface_name] = new_routes

    def gen_metadata(self, ifaces):
        """
        Generate metada which could used for storing into interface.
        Data structure returned is:
            {
                iface_name: {
                    Interface.IPV4: ipv4_routes,
                    Interface.IPV6: ipv6_routes,
                }
            }
        """
        route_metadata = {}
        for iface_name, route_set in self._routes.items():
            route_metadata[iface_name] = {
                Interface.IPV4: [],
                Interface.IPV6: [],
            }
            if route_set != self._cur_routes[iface_name]:
                route_metadata[iface_name][
                    BaseIface.ROUTE_CHANGED_METADATA
                ] = True
            for route in route_set:
                family = Interface.IPV6 if route.is_ipv6 else Interface.IPV4
                route_metadata[iface_name][family].append(route.to_dict())
        return route_metadata

    @property
    def config_iface_routes(self):
        """
        Return configured routes indexed by next hop interface
        """
        if list(self._routes.values()) == [set()]:
            return {}
        return self._routes

    def verify(self, cur_route_state):
        current = RouteState(
            ifaces=None, des_route_state=None, cur_route_state=cur_route_state
        )
        for iface_name, route_set in self._routes.items():
            cur_route_set = current._routes.get(iface_name, set())
            # Kernel might append additional routes. For example, IPv6 default
            # gateway will generate /128 static direct route
            if not route_set <= cur_route_set:
                routes_info = [
                    r.to_dict() for r in sorted(route_set) if not r.absent
                ]
                cur_routes_info = [r.to_dict() for r in sorted(cur_route_set)]
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        {Route.KEY: {Route.CONFIG: routes_info}},
                        {Route.KEY: {Route.CONFIG: cur_routes_info}},
                    )
                )
