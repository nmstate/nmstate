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
from libnmstate.nm import dns as nm_dns
from libnmstate.nm import route as nm_route
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import Route

from ..ifaces import BaseIface
from .common import NM

IPV6_DEFAULT_ROUTE_METRIC = 1024
INT32_MAX = 2**31 - 1


def get_info(active_connection, applied_config):
    """
    Provide information regarding:
        * Enable status
        * DHCP/Autoconf status
    """
    if active_connection is None or applied_config is None:
        # Neither unmanaged or not active, let nispor determine its state
        return {}

    info = {
        InterfaceIPv6.ENABLED: False,
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.AUTOCONF: False,
    }

    ip_profile = (
        applied_config.get_setting_ip6_config() if applied_config else None
    )
    if ip_profile:
        info[InterfaceIPv6.ENABLED] = True
        method = ip_profile.get_method()
        if method == NM.SETTING_IP6_CONFIG_METHOD_AUTO:
            info[InterfaceIPv6.DHCP] = True
            info[InterfaceIPv6.AUTOCONF] = True
        elif method == NM.SETTING_IP6_CONFIG_METHOD_DHCP:
            info[InterfaceIPv6.DHCP] = True
            info[InterfaceIPv6.AUTOCONF] = False
        elif method == NM.SETTING_IP6_CONFIG_METHOD_DISABLED:
            info[InterfaceIPv6.ENABLED] = False

        if info[InterfaceIPv6.DHCP] or info[InterfaceIPv6.AUTOCONF]:
            props = ip_profile.props
            info[InterfaceIPv6.AUTO_ROUTES] = not props.ignore_auto_routes
            info[InterfaceIPv6.AUTO_GATEWAY] = not props.never_default
            info[InterfaceIPv6.AUTO_DNS] = not props.ignore_auto_dns
            info[InterfaceIPv6.AUTO_ROUTE_TABLE_ID] = props.route_table
            if props.dhcp_duid:
                info[InterfaceIPv6.DHCP_DUID] = props.dhcp_duid
            if props.route_metric > 0:
                info[InterfaceIPv6.AUTO_ROUTE_METRIC] = props.route_metric
            info[InterfaceIPv6.ADDR_GEN_MODE] = (
                InterfaceIPv6.ADDR_GEN_MODE_STABLE_PRIVACY
                if props.addr_gen_mode
                else InterfaceIPv6.ADDR_GEN_MODE_EUI64
            )

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
            setting_ip.clear_routing_rules()
            setting_ip.props.gateway = None
            setting_ip.props.route_table = Route.USE_DEFAULT_ROUTE_TABLE
            setting_ip.props.route_metric = Route.USE_DEFAULT_METRIC
            setting_ip.clear_dns()
            setting_ip.clear_dns_searches()
            setting_ip.props.dns_priority = nm_dns.DEFAULT_DNS_PRIORITY

    if not setting_ip:
        setting_ip = NM.SettingIP6Config.new()

    # Ensure IPv6 RA and DHCPv6 is based on MAC address only
    setting_ip.props.addr_gen_mode = NM.SettingIP6ConfigAddrGenMode.EUI64
    setting_ip.props.dhcp_duid = "ll"
    setting_ip.props.dhcp_iaid = "mac"

    if not config or not config.get(InterfaceIPv6.ENABLED):
        setting_ip.props.method = NM.SETTING_IP6_CONFIG_METHOD_DISABLED
        return setting_ip

    is_dhcp = config.get(InterfaceIPv6.DHCP, False)
    is_autoconf = config.get(InterfaceIPv6.AUTOCONF, False)
    ip_addresses = config.get(InterfaceIPv6.ADDRESS, ())

    if is_dhcp or is_autoconf:
        _set_dynamic(setting_ip, is_dhcp, is_autoconf)
        # NetworkManager will remove the virtual interface when DHCPv6 or
        # IPv6-RA timeout, set them to infinity.
        setting_ip.props.dhcp_timeout = INT32_MAX
        setting_ip.props.ra_timeout = INT32_MAX
        setting_ip.props.ignore_auto_routes = not config.get(
            InterfaceIPv6.AUTO_ROUTES, True
        )
        setting_ip.props.never_default = not config.get(
            InterfaceIPv6.AUTO_GATEWAY, True
        )
        setting_ip.props.ignore_auto_dns = not config.get(
            InterfaceIPv6.AUTO_DNS, True
        )
        setting_ip.props.dhcp_duid = config.get(InterfaceIPv6.DHCP_DUID, None)
        addr_gen_mode = config.get(InterfaceIPv6.ADDR_GEN_MODE, None)
        if (
            addr_gen_mode == InterfaceIPv6.ADDR_GEN_MODE_EUI64
            or addr_gen_mode is None
        ):
            setting_ip.props.addr_gen_mode = 0
        else:
            setting_ip.props.addr_gen_mode = 1

        route_table = config.get(InterfaceIPv6.AUTO_ROUTE_TABLE_ID)
        if route_table:
            setting_ip.props.route_table = route_table

        route_metric = config.get(InterfaceIPv6.AUTO_ROUTE_METRIC)
        if route_metric is not None:
            setting_ip.props.route_metric = route_metric

    elif ip_addresses:
        _set_static(setting_ip, ip_addresses)
    else:
        setting_ip.props.method = NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL

    nm_route.add_routes(setting_ip, config.get(BaseIface.ROUTES_METADATA, []))
    nm_dns.add_dns(setting_ip, config.get(BaseIface.DNS_METADATA, {}))
    nm_route.add_route_rules(
        setting_ip,
        socket.AF_INET6,
        config.get(BaseIface.ROUTE_RULES_METADATA, []),
    )
    return setting_ip


def _set_dynamic(setting_ip, is_dhcp, is_autoconf):
    if not is_dhcp and is_autoconf:
        raise NmstateNotImplementedError(
            "Autoconf without DHCP is not supported yet"
        )

    if is_dhcp and is_autoconf:
        setting_ip.props.method = NM.SETTING_IP6_CONFIG_METHOD_AUTO
    elif is_dhcp and not is_autoconf:
        setting_ip.props.method = NM.SETTING_IP6_CONFIG_METHOD_DHCP


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
            naddr = NM.IPAddress.new(
                socket.AF_INET6,
                address[InterfaceIPv6.ADDRESS_IP],
                address[InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
            )
            setting_ip.add_address(naddr)

    if setting_ip.props.addresses:
        setting_ip.props.method = NM.SETTING_IP6_CONFIG_METHOD_MANUAL
    else:
        setting_ip.props.method = NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL


def get_ip_profile(active_connection):
    """
    Get NMSettingIP6Config from NMActiveConnection.
    For any error, return None.
    """
    remote_conn = active_connection.get_connection()
    if remote_conn:
        return remote_conn.get_setting_ip6_config()
    return None


def acs_and_ip_profiles(nm_client):
    for ac in nm_client.get_active_connections():
        ip_profile = get_ip_profile(ac)
        if not ip_profile:
            continue
        yield ac, ip_profile


def is_dynamic(active_connection):
    ip_profile = get_ip_profile(active_connection)
    if ip_profile:
        method = ip_profile.get_method()
        return method in (
            NM.SETTING_IP6_CONFIG_METHOD_AUTO,
            NM.SETTING_IP6_CONFIG_METHOD_DHCP,
        )
    return False
