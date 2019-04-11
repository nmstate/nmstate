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
from operator import itemgetter

from libnmstate import iplib
from libnmstate.error import NmstateInternalError
from libnmstate.nm import nmclient
from libnmstate.nm import ipv4 as nm_ipv4
from libnmstate.nm import ipv6 as nm_ipv6
from libnmstate.schema import DNS


DNS_DEFAULT_PRIORITY_VPN = 50
DNS_DEFAULT_PRIORITY_OTHER = 100

IPV6_ADDRESS_LENGTH = 128


def get_running():
    dns_state = {
        DNS.SERVER: [],
        DNS.SEARCH: []
    }
    client = nmclient.client()
    for dns_conf in client.get_dns_configuration():
        iface_name = dns_conf.get_interface()
        for ns in dns_conf.get_nameservers():
            if iplib.is_ipv6_link_local_addr(ns, IPV6_ADDRESS_LENGTH):
                if not iface_name:
                    # For IPv6 link local address, the interface name should be
                    # appended also.
                    raise NmstateInternalError(
                        'Missing interface for IPv6 link-local DNS server '
                        'entry {}'.format(ns))
                ns_addr = '{}%{}'.format(ns, iface_name)
            else:
                ns_addr = ns
            dns_state[DNS.SERVER].append(ns_addr)
        dns_state[DNS.SEARCH].extend(dns_conf.get_domains())
    if not dns_state[DNS.SERVER] and not dns_state[DNS.SEARCH]:
        dns_state = {}
    return dns_state


def get_config():
    dns_conf = {
        DNS.SERVER: [],
        DNS.SEARCH: []
    }
    tmp_dns_confs = []
    client = nmclient.client()
    for ac in client.get_active_connections():
        # NM prefers IPv6 over IPv4 DNS.
        for ip_profile in (nm_ipv6.get_ip_profile(ac),
                           nm_ipv4.get_ip_profile(ac)):
            if not ip_profile:
                continue
            if not ip_profile.props.dns and not ip_profile.props.dns_search:
                continue
            priority = ip_profile.props.dns_priority
            if priority == 0:
                # ^ The dns_priority in 'NetworkManager.conf' is been ignored
                #   due to the lacking of query function in libnm API.
                if ac.get_vpn():
                    priority = DNS_DEFAULT_PRIORITY_VPN
                else:
                    priority = DNS_DEFAULT_PRIORITY_OTHER

            tmp_dns_confs.append(
                {
                    'server': ip_profile.props.dns,
                    'priority': priority,
                    'search': ip_profile.props.dns_search,
                }
            )
    # NetworkManager sorts the DNS entries based on various criteria including
    # which profile was activated first when profiles are activated. Therefore
    # the configuration does not completely define the order. To define the
    # order in a declarative way, Nmstate only uses the priority to order the
    # entries. Reference:
    # https://developer.gnome.org/NetworkManager/stable/nm-settings.html#nm-settings.property.ipv4.dns-priority
    tmp_dns_confs.sort(key=itemgetter('priority'))
    for e in tmp_dns_confs:
        dns_conf[DNS.SERVER].extend(e['server'])
        dns_conf[DNS.SEARCH].extend(e['search'])
    if not dns_conf[DNS.SERVER] and dns_conf[DNS.SEARCH]:
        return {}
    return dns_conf
