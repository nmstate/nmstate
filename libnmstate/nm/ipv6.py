#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

import logging
import socket

from libnmstate import iplib
from libnmstate.error import NmstateNotImplementedError
from libnmstate.nm import nmclient
from libnmstate.nm import dns as nm_dns
from libnmstate.nm import route as nm_route
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import Route


IPV6_DEFAULT_ROUTE_METRIC = 1024


def get_info(active_connection):
    info = {InterfaceIPv6.ENABLED: False}
    if active_connection is None:
        return info

    info[InterfaceIPv6.DHCP] = False
    info[InterfaceIPv6.AUTOCONF] = False

    is_link_local_method = False
    ip_profile = get_ip_profile(active_connection)
    if ip_profile:
        method = ip_profile.get_method()
        if method == nmclient.NM.SETTING_IP6_CONFIG_METHOD_AUTO:
            info[InterfaceIPv6.DHCP] = True
            info[InterfaceIPv6.AUTOCONF] = True
        elif method == nmclient.NM.SETTING_IP6_CONFIG_METHOD_DHCP:
            info[InterfaceIPv6.DHCP] = True
            info[InterfaceIPv6.AUTOCONF] = False
        elif method == nmclient.NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL:
            is_link_local_method = True
        elif method == nmclient.NM.SETTING_IP6_CONFIG_METHOD_DISABLED:
            return info

        if info[InterfaceIPv6.DHCP] or info[InterfaceIPv6.AUTOCONF]:
            props = ip_profile.props
            info[InterfaceIPv6.AUTO_ROUTES] = not props.ignore_auto_routes
            info[InterfaceIPv6.AUTO_GATEWAY] = not props.never_default
            info[InterfaceIPv6.AUTO_DNS] = not props.ignore_auto_dns

    ipconfig = active_connection.get_ip6_config()
    if ipconfig is None:
        # When DHCP is enable, it might be possible, the active_connection does
        # not got IP address yet. In that case, we still mark
        # info[InterfaceIPv6.ENABLED] as True.
        if (
            info[InterfaceIPv6.DHCP]
            or info[InterfaceIPv6.AUTOCONF]
            or is_link_local_method
        ):
            info[InterfaceIPv6.ENABLED] = True
            info[InterfaceIPv6.ADDRESS] = []
        else:
            del info[InterfaceIPv6.DHCP]
            del info[InterfaceIPv6.AUTOCONF]
        return info

    addresses = [
        {
            InterfaceIPv6.ADDRESS_IP: address.get_address(),
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: int(address.get_prefix()),
        }
        for address in ipconfig.get_addresses()
    ]
    if not addresses:
        return info

    info[InterfaceIPv6.ENABLED] = True
    info[InterfaceIPv6.ADDRESS] = addresses
    return info


def create_setting(config, base_con_profile):
    setting_ip = None
    if base_con_profile and config and config.get(InterfaceIPv6.ENABLED):
        setting_ip = base_con_profile.get_setting_ip6_config()
        if setting_ip:
            setting_ip = setting_ip.duplicate()
            setting_ip.clear_addresses()
            setting_ip.props.ignore_auto_routes = False
            setting_ip.props.never_default = False
            setting_ip.props.ignore_auto_dns = False
            setting_ip.clear_routes()
            setting_ip.props.gateway = None
            setting_ip.props.route_table = Route.USE_DEFAULT_ROUTE_TABLE
            setting_ip.props.route_metric = Route.USE_DEFAULT_METRIC
            setting_ip.clear_dns()
            setting_ip.clear_dns_searches()
            setting_ip.props.dns_priority = nm_dns.DEFAULT_DNS_PRIORITY

    if not setting_ip:
        setting_ip = nmclient.NM.SettingIP6Config.new()

    # Ensure IPv6 RA and DHCPv6 is based on MAC address only
    setting_ip.props.addr_gen_mode = (
        nmclient.NM.SettingIP6ConfigAddrGenMode.EUI64
    )
    setting_ip.props.dhcp_duid = "ll"
    setting_ip.props.dhcp_iaid = "mac"

    if not config or not config.get(InterfaceIPv6.ENABLED):
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_DISABLED
        )
        return setting_ip

    is_dhcp = config.get(InterfaceIPv6.DHCP, False)
    is_autoconf = config.get(InterfaceIPv6.AUTOCONF, False)
    ip_addresses = config.get(InterfaceIPv6.ADDRESS, ())

    if is_dhcp or is_autoconf:
        _set_dynamic(setting_ip, is_dhcp, is_autoconf)
        setting_ip.props.ignore_auto_routes = not config.get(
            InterfaceIPv6.AUTO_ROUTES, True
        )
        setting_ip.props.never_default = not config.get(
            InterfaceIPv6.AUTO_GATEWAY, True
        )
        setting_ip.props.ignore_auto_dns = not config.get(
            InterfaceIPv6.AUTO_DNS, True
        )
    elif ip_addresses:
        _set_static(setting_ip, ip_addresses)
    else:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL
        )

    nm_route.add_routes(setting_ip, config.get(nm_route.ROUTE_METADATA, []))
    nm_dns.add_dns(setting_ip, config.get(nm_dns.DNS_METADATA, {}))
    nm_route.add_route_rules(
        setting_ip,
        socket.AF_INET6,
        config.get(nm_route.ROUTE_RULES_METADATA, []),
    )
    return setting_ip


def _set_dynamic(setting_ip, is_dhcp, is_autoconf):
    if not is_dhcp and is_autoconf:
        raise NmstateNotImplementedError(
            "Autoconf without DHCP is not supported yet"
        )

    if is_dhcp and is_autoconf:
        setting_ip.props.method = nmclient.NM.SETTING_IP6_CONFIG_METHOD_AUTO
    elif is_dhcp and not is_autoconf:
        setting_ip.props.method = nmclient.NM.SETTING_IP6_CONFIG_METHOD_DHCP


def _set_static(setting_ip, ip_addresses):
    for address in ip_addresses:
        if iplib.is_ipv6_link_local_addr(
            address[InterfaceIPv6.ADDRESS_IP],
            address[InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
        ):
            logging.warning(
                "IPv6 link local address "
                "{a[ip]}/{a[prefix-length]} is ignored "
                "when applying desired state".format(a=address)
            )
        else:
            naddr = nmclient.NM.IPAddress.new(
                socket.AF_INET6,
                address[InterfaceIPv6.ADDRESS_IP],
                address[InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
            )
            setting_ip.add_address(naddr)

    if setting_ip.props.addresses:
        setting_ip.props.method = nmclient.NM.SETTING_IP6_CONFIG_METHOD_MANUAL
    else:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL
        )


def get_ip_profile(active_connection):
    """
    Get NMSettingIP6Config from NMActiveConnection.
    For any error, return None.
    """
    remote_conn = active_connection.get_connection()
    if remote_conn:
        return remote_conn.get_setting_ip6_config()
    return None


def get_route_running():
    return nm_route.get_running(_acs_and_ip_cfgs(nmclient.client()))


def get_route_config():
    routes = nm_route.get_config(acs_and_ip_profiles(nmclient.client()))
    for route in routes:
        if route[Route.METRIC] == 0:
            # Kernel will convert 0 to IPV6_DEFAULT_ROUTE_METRIC.
            route[Route.METRIC] = IPV6_DEFAULT_ROUTE_METRIC

    return routes


def _acs_and_ip_cfgs(client):
    for ac in client.get_active_connections():
        ip_cfg = ac.get_ip6_config()
        if not ip_cfg:
            continue
        yield ac, ip_cfg


def acs_and_ip_profiles(client):
    for ac in client.get_active_connections():
        ip_profile = get_ip_profile(ac)
        if not ip_profile:
            continue
        yield ac, ip_profile


def is_dynamic(active_connection):
    ip_profile = get_ip_profile(active_connection)
    if ip_profile:
        method = ip_profile.get_method()
        return method in (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_DHCP,
        )
    return False


def get_routing_rule_config():
    return nm_route.get_routing_rule_config(
        acs_and_ip_profiles(nmclient.client())
    )
