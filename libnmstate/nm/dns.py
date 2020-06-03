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

from itertools import chain
from operator import itemgetter

from libnmstate import iplib
from libnmstate.dns import DnsState
from libnmstate.error import NmstateInternalError
from libnmstate.nm import active_connection as nm_ac
from libnmstate.schema import DNS


DNS_DEFAULT_PRIORITY_VPN = 50
DNS_DEFAULT_PRIORITY_OTHER = 100
DEFAULT_DNS_PRIORITY = 0
# The 40 is chose as default DHCP DNS priority is 100, and VPN DNS priority is
# 50, the static DNS configuration should be list before them.
DNS_PRIORITY_STATIC_BASE = 40

IPV6_ADDRESS_LENGTH = 128


def get_running(context):
    dns_state = {DNS.SERVER: [], DNS.SEARCH: []}
    for dns_conf in context.get_dns_configuration():
        iface_name = dns_conf.get_interface()
        for ns in dns_conf.get_nameservers():
            if iplib.is_ipv6_link_local_addr(ns, IPV6_ADDRESS_LENGTH):
                if not iface_name:
                    # For IPv6 link local address, the interface name should be
                    # appended also.
                    raise NmstateInternalError(
                        "Missing interface for IPv6 link-local DNS server "
                        "entry {}".format(ns)
                    )
                ns_addr = "{}%{}".format(ns, iface_name)
            else:
                ns_addr = ns
            if ns_addr not in dns_state[DNS.SERVER]:
                dns_state[DNS.SERVER].append(ns_addr)
        dns_domains = [
            dns_domain
            for dns_domain in dns_conf.get_domains()
            if dns_domain not in dns_state[DNS.SEARCH]
        ]
        dns_state[DNS.SEARCH].extend(dns_domains)
    if not dns_state[DNS.SERVER] and not dns_state[DNS.SEARCH]:
        dns_state = {}
    return dns_state


def get_config(acs_and_ipv4_profiles, acs_and_ipv6_profiles):
    dns_conf = {DNS.SERVER: [], DNS.SEARCH: []}
    tmp_dns_confs = []
    for ac, ip_profile in chain(acs_and_ipv6_profiles, acs_and_ipv4_profiles):
        if not ip_profile.props.dns and not ip_profile.props.dns_search:
            continue
        priority = ip_profile.props.dns_priority
        if priority == DEFAULT_DNS_PRIORITY:
            # ^ The dns_priority in 'NetworkManager.conf' is been ignored
            #   due to the lacking of query function in libnm API.
            if ac.get_vpn():
                priority = DNS_DEFAULT_PRIORITY_VPN
            else:
                priority = DNS_DEFAULT_PRIORITY_OTHER

        tmp_dns_confs.append(
            {
                "server": ip_profile.props.dns,
                "priority": priority,
                "search": ip_profile.props.dns_search,
            }
        )
    # NetworkManager sorts the DNS entries based on various criteria including
    # which profile was activated first when profiles are activated. Therefore
    # the configuration does not completely define the order. To define the
    # order in a declarative way, Nmstate only uses the priority to order the
    # entries. Reference:
    # https://developer.gnome.org/NetworkManager/stable/nm-settings.html#nm-settings.property.ipv4.dns-priority
    tmp_dns_confs.sort(key=itemgetter("priority"))
    for e in tmp_dns_confs:
        dns_conf[DNS.SERVER].extend(e["server"])
        dns_conf[DNS.SEARCH].extend(e["search"])
    if not dns_conf[DNS.SERVER] and dns_conf[DNS.SEARCH]:
        return {}
    return dns_conf


def add_dns(setting_ip, dns_state):
    priority = dns_state.get(DnsState.PRIORITY_METADATA)
    if priority is not None:
        setting_ip.props.dns_priority = priority + DNS_PRIORITY_STATIC_BASE
    for server in dns_state.get(DNS.SERVER, []):
        setting_ip.add_dns(server)
    for search in dns_state.get(DNS.SEARCH, []):
        setting_ip.add_dns_search(search)


def get_dns_config_iface_names(acs_and_ipv4_profiles, acs_and_ipv6_profiles):
    """
    Return a list of interface names which hold static DNS configuration.
    """
    iface_names = []
    for ac, ip_profile in chain(acs_and_ipv6_profiles, acs_and_ipv4_profiles):
        if ip_profile.props.dns or ip_profile.props.dns_search:
            iface_names.append(nm_ac.ActiveConnection(nm_ac_con=ac).devname)
    return iface_names
