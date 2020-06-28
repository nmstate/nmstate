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

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.iplib import is_ipv6_address
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import DNS
from libnmstate.schema import Interface


class DnsState:
    PRIORITY_METADATA = "_priority"

    def __init__(self, des_dns_state, cur_dns_state):
        self._config_changed = False
        if des_dns_state is None or des_dns_state.get(DNS.CONFIG) is None:
            # Use current config if DNS.KEY not defined or DNS.CONFIG not
            # defined.
            self._dns_state = cur_dns_state or {}
        else:
            self._dns_state = des_dns_state
            self._validate()
            self._config_changed = _is_dns_config_changed(
                des_dns_state, cur_dns_state
            )
        self._cur_dns_state = deepcopy(cur_dns_state) if cur_dns_state else {}

    @property
    def current_config(self):
        return _get_config(self._cur_dns_state)

    @property
    def config(self):
        return _get_config(self._dns_state)

    @property
    def _config_servers(self):
        return _get_config_servers(self._dns_state)

    @property
    def _config_searches(self):
        return _get_config_searches(self._dns_state)

    def gen_metadata(self, ifaces, route_state):
        """
        Return DNS configure targeting to store as metadata of interface.
        Data structure returned is:
            {
                iface_name: {
                    Interface.IPV4: {
                        DNS.SERVER: dns_servers,
                        DNS.SEARCH: dns_searches,
                    },
                    Interface.IPV6: {
                        DNS.SERVER: dns_servers,
                        DNS.SEARCH: dns_searches,
                    },
                }
            }
        """
        iface_metadata = {}
        if not self._config_servers and not self._config_searches:
            return iface_metadata
        ipv4_iface, ipv6_iface = self._find_ifaces_for_name_servers(
            ifaces, route_state
        )
        if ipv4_iface == ipv6_iface:
            iface_metadata = {
                ipv4_iface: {
                    Interface.IPV4: {DNS.SERVER: [], DNS.SEARCH: []},
                    Interface.IPV6: {DNS.SERVER: [], DNS.SEARCH: []},
                },
            }
        else:
            if ipv4_iface:
                iface_metadata[ipv4_iface] = {
                    Interface.IPV4: {DNS.SERVER: [], DNS.SEARCH: []},
                }
            if ipv6_iface:
                iface_metadata[ipv6_iface] = {
                    Interface.IPV6: {DNS.SERVER: [], DNS.SEARCH: []},
                }
        index = 0
        searches_saved = False
        for server in self._config_servers:
            iface_name = None
            if is_ipv6_address(server):
                iface_name = ipv6_iface
                family = Interface.IPV6
            else:
                iface_name = ipv4_iface
                family = Interface.IPV4
            if not iface_name:
                raise NmstateValueError(
                    "Failed to find suitable interface for saving DNS "
                    "name servers: %s" % server
                )
            iface_dns_metada = iface_metadata[iface_name][family]
            iface_dns_metada[DNS.SERVER].append(server)
            iface_dns_metada.setdefault(DnsState.PRIORITY_METADATA, index)
            if not searches_saved:
                iface_dns_metada[DNS.SEARCH] = self._config_searches
            searches_saved = True
            index += 1
        return iface_metadata

    def _find_ifaces_for_name_servers(self, ifaces, route_state):
        """
        Find interface to store the DNS configurations in the order of:
            * Any interface with static gateway
            * Any interface configured as dynamic IP with 'auto-dns:False'
        Return tuple: (ipv4_iface, ipv6_iface)
        """
        ipv4_iface, ipv6_iface = self._find_ifaces_with_static_gateways(
            route_state
        )
        if not (ipv4_iface and ipv6_iface):
            (
                auto_ipv4_iface,
                auto_ipv6_iface,
            ) = self._find_ifaces_with_auto_dns_false(ifaces)
            if not ipv4_iface and auto_ipv4_iface:
                ipv4_iface = auto_ipv4_iface
            if not ipv6_iface and auto_ipv6_iface:
                ipv6_iface = auto_ipv6_iface

        return ipv4_iface, ipv6_iface

    def _find_ifaces_with_static_gateways(self, route_state):
        """
        Return tuple of interfaces with IPv4 and IPv6 static gateways.
        """
        ipv4_iface = None
        ipv6_iface = None
        for iface_name, route_set in route_state.config_iface_routes.items():
            for route in route_set:
                if ipv4_iface and ipv6_iface:
                    return (ipv4_iface, ipv6_iface)
                if route.is_gateway:
                    if route.is_ipv6:
                        ipv6_iface = iface_name
                    else:
                        ipv4_iface = iface_name
        return (ipv4_iface, ipv6_iface)

    def _find_ifaces_with_auto_dns_false(self, ifaces):
        ipv4_iface = None
        ipv6_iface = None
        for iface in ifaces.values():
            if ipv4_iface and ipv6_iface:
                return (ipv4_iface, ipv6_iface)
            for family in (Interface.IPV4, Interface.IPV6):
                ip_state = iface.ip_state(family)
                if ip_state.is_dynamic and (not ip_state.auto_dns):
                    if family == Interface.IPV4:
                        ipv4_iface = iface.name
                    else:
                        ipv6_iface = iface.name

        return (ipv4_iface, ipv6_iface)

    def verify(self, cur_dns_state):
        cur_dns = DnsState(des_dns_state=None, cur_dns_state=cur_dns_state,)
        if self.config.get(DNS.SERVER) != cur_dns.config.get(
            DNS.SERVER
        ) or self.config.get(DNS.SEARCH) != cur_dns.config.get(DNS.SEARCH):
            raise NmstateVerificationError(
                format_desired_current_state_diff(
                    {DNS.KEY: self.config}, {DNS.KEY: cur_dns.config},
                )
            )

    def _validate(self):
        if (
            len(self._config_servers) > 2
            and any(is_ipv6_address(n) for n in self._config_servers)
            and any(not is_ipv6_address(n) for n in self._config_servers)
        ):
            raise NmstateNotImplementedError(
                "Three or more nameservers are only supported when using "
                "either IPv4 or IPv6 nameservers but not both."
            )

    @property
    def config_changed(self):
        return self._config_changed


def _get_config(state):
    conf = state.get(DNS.CONFIG, {})
    if not conf:
        conf = {DNS.SERVER: [], DNS.SEARCH: []}
    return conf


def _get_config_servers(state):
    return _get_config(state).get(DNS.SERVER, [])


def _get_config_searches(state):
    return _get_config(state).get(DNS.SEARCH, [])


def _is_dns_config_changed(des_dns_state, cur_dns_state):
    return _get_config_servers(des_dns_state) != _get_config_servers(
        cur_dns_state
    ) or _get_config_searches(des_dns_state) != _get_config_searches(
        cur_dns_state
    )
