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

from collections import defaultdict

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.iplib import is_ipv6_address
from libnmstate.iplib import canonicalize_ip_network
from libnmstate.iplib import canonicalize_ip_address
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Interface
from libnmstate.schema import Route

from .state import StateEntry
from .state import state_match


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
        iface = ifaces.get(self.next_hop_interface)
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
        if des_route_state:
            self._merge_routes(des_route_state, ifaces)

    def _merge_routes(self, des_route_state, ifaces):
        # Handle absent route before adding desired route entries to
        # make sure absent route does not delete route defined in
        # desire state
        for entry in des_route_state.get(Route.CONFIG, []):
            rt = RouteEntry(entry)
            if rt.absent:
                self._apply_absent_routes(rt, ifaces)
        for entry in des_route_state.get(Route.CONFIG, []):
            rt = RouteEntry(entry)
            if not rt.absent:
                if rt.is_valid(ifaces):
                    ifaces[rt.next_hop_interface].mark_as_changed()
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
            if new_routes != route_set:
                ifaces[iface_name].mark_as_changed()
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
            routes_info = [r.to_dict() for r in sorted(route_set)]
            cur_routes_info = [
                r.to_dict()
                for r in sorted(current._routes.get(iface_name, set()))
            ]
            if not state_match(routes_info, cur_routes_info):
                raise NmstateVerificationError(
                    format_desired_current_state_diff(
                        {Route.KEY: {Route.CONFIG: routes_info}},
                        {Route.KEY: {Route.CONFIG: cur_routes_info}},
                    )
                )
