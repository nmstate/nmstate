# SPDX-License-Identifier: LGPL-2.1-or-later

from copy import deepcopy

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.iplib import canonicalize_ip_address
from libnmstate.iplib import is_ipv6_address
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import DNS
from libnmstate.schema import Interface

REMOVE_DNS_CONFIG = {
    DNS.CONFIG: {
        DNS.SERVER: [],
        DNS.SEARCH: [],
    }
}


class DnsState:
    PRIORITY_METADATA = "_priority"

    def __init__(self, des_dns_state, cur_dns_state):
        self._config_changed = False
        self._cur_dns_state = deepcopy(cur_dns_state) if cur_dns_state else {}
        self._dns_state = merge_dns(des_dns_state, cur_dns_state or {})
        if des_dns_state and des_dns_state.get(DNS.CONFIG):
            if cur_dns_state:
                self._config_changed = _is_dns_config_changed(
                    des_dns_state, cur_dns_state
                )
        self._canonicalize_ip_address()

    def _canonicalize_ip_address(self):
        canonicalized_addrs = [
            canonicalize_ip_address(address) for address in self.config_servers
        ]
        self.config[DNS.SERVER] = canonicalized_addrs

    @property
    def current_config(self):
        return _get_config(self._cur_dns_state)

    @property
    def config(self):
        return _get_config(self._dns_state)

    @property
    def config_servers(self):
        return _get_config_servers(self._dns_state)

    @property
    def config_searches(self):
        return _get_config_searches(self._dns_state)

    def gen_metadata(self, ifaces, route_state, ignored_dns_ifaces):
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
        if not self.config_servers and not self.config_searches:
            return iface_metadata

        ipv4_iface, ipv6_iface = self._find_ifaces_for_name_servers(
            ifaces, route_state, ignored_dns_ifaces
        )
        if ipv4_iface == ipv6_iface and ipv4_iface:
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
        for server in self.config_servers:
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
                    "name servers: %s, nmstate only support saving DNS to "
                    "interface with static gateway or auto interface with "
                    "auto-dns:false" % server
                )
            iface_dns_metada = iface_metadata[iface_name][family]
            iface_dns_metada[DNS.SERVER].append(server)
            iface_dns_metada.setdefault(DnsState.PRIORITY_METADATA, index)
            if not searches_saved:
                iface_dns_metada[DNS.SEARCH] = self.config_searches
            searches_saved = True
            index += 1

        return iface_metadata

    def _find_ifaces_for_name_servers(
        self, ifaces, route_state, ignored_dns_ifaces
    ):
        """
        Find interface to store the DNS configurations in the order of:
            * Any interface with static gateway
            * Any interface configured as dynamic IP with 'auto-dns:False'
        The loopback interface is ignored.
        Return tuple: (ipv4_iface, ipv6_iface)
        """
        ipv4_iface, ipv6_iface = self._find_ifaces_with_static_gateways(
            ifaces,
            route_state,
            ignored_dns_ifaces,
        )
        if not (ipv4_iface and ipv6_iface):
            (
                auto_ipv4_iface,
                auto_ipv6_iface,
            ) = self._find_ifaces_with_auto_dns_false(
                ifaces, ignored_dns_ifaces
            )
            if not ipv4_iface and auto_ipv4_iface:
                ipv4_iface = auto_ipv4_iface
            if not ipv6_iface and auto_ipv6_iface:
                ipv6_iface = auto_ipv6_iface

        return ipv4_iface, ipv6_iface

    def _find_ifaces_with_static_gateways(
        self, ifaces, route_state, ignored_dns_ifaces
    ):
        """
        Return tuple of interfaces with IPv4 and IPv6 static gateways.
        """
        ipv4_iface = None
        ipv6_iface = None
        for iface_name, route_set in route_state.config_iface_routes.items():
            if iface_name == "lo":
                continue

            for route in route_set:
                if ipv4_iface and ipv6_iface:
                    return (ipv4_iface, ipv6_iface)
                if route.is_gateway:
                    iface = ifaces.all_kernel_ifaces.get(iface_name)
                    if not iface:
                        continue
                    # Skip ignored interface
                    if iface.is_ignore:
                        continue
                    # Skip plugin blacklist of DNS interface
                    if (
                        not iface.is_changed
                        and not iface.is_desired
                        and iface_name in ignored_dns_ifaces
                    ):
                        continue
                    if route.is_ipv6:
                        ipv6_iface = iface_name
                    else:
                        ipv4_iface = iface_name
        return (ipv4_iface, ipv6_iface)

    def _find_ifaces_with_auto_dns_false(self, ifaces, ignored_dns_ifaces):
        ipv4_iface = None
        ipv6_iface = None
        for iface in ifaces.all_kernel_ifaces.values():
            if iface.is_ignore or (
                iface.name in ignored_dns_ifaces
                and not iface.is_changed
                and not iface.is_desired
            ):
                continue
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
        cur_dns = DnsState(
            des_dns_state=None,
            cur_dns_state=cur_dns_state,
        )
        if self.config.get(DNS.SERVER, []) != cur_dns.config.get(
            DNS.SERVER, []
        ) or self.config.get(DNS.SEARCH, []) != cur_dns.config.get(
            DNS.SEARCH, []
        ):
            raise NmstateVerificationError(
                format_desired_current_state_diff(
                    {DNS.KEY: self.config},
                    {DNS.KEY: cur_dns.config},
                )
            )

    def is_46_mixed_dns_servers(self):
        return (
            len(self.config_servers) > 2
            and any(is_ipv6_address(n) for n in self.config_servers)
            and any(not is_ipv6_address(n) for n in self.config_servers)
            and _is_mixed_dns_servers(self.config_servers)
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


def _is_mixed_dns_servers(servers):
    """
    Return True when an IPv6 server is in the middle of two IPv4 namesevers or
    an IPv4 server is in the middle of two IPv6 servers.
    """
    pattern = ""
    for server in servers:
        if is_ipv6_address(server):
            pattern += "6"
        else:
            pattern += "4"

    return "464" in pattern or "646" in pattern


def merge_dns(desire, current):
    """
    * When non-empty desire dns search, copy dns server from current when
      undefined.
    * When non-empty desire dns sever, copy dns search from current when
      undefined.
    """
    if desire is None:
        return deepcopy(current)

    if desire.get(DNS.CONFIG) == {}:
        return deepcopy(REMOVE_DNS_CONFIG)

    des_servers = desire.get(DNS.CONFIG, {}).get(DNS.SERVER)
    cur_servers = current.get(DNS.CONFIG, {}).get(DNS.SERVER)
    des_searches = desire.get(DNS.CONFIG, {}).get(DNS.SEARCH)
    cur_searches = current.get(DNS.CONFIG, {}).get(DNS.SEARCH)

    if des_servers is None and des_searches is None:
        # When desire not mentioned, use current config.
        return deepcopy(current)

    if des_servers is None:
        des_servers = deepcopy(cur_servers) if cur_servers else []
    if des_searches is None:
        des_searches = deepcopy(cur_searches) if cur_searches else []

    return {
        DNS.RUNNING: deepcopy(current.get(DNS.RUNNING, {})),
        DNS.CONFIG: {
            DNS.SERVER: des_servers,
            DNS.SEARCH: des_searches,
        },
    }
