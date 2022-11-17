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

import socket

from libnmstate.nm import dns as nm_dns
from libnmstate.nm import route as nm_route
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import Route

from ..ifaces import BaseIface
from .common import NM

INT32_MAX = 2**31 - 1


def create_setting(config, base_con_profile):
    setting_ipv4 = None
    if base_con_profile and config and config.get(InterfaceIPv4.ENABLED):
        setting_ipv4 = base_con_profile.get_setting_ip4_config()
        if setting_ipv4:
            setting_ipv4 = setting_ipv4.duplicate()
            setting_ipv4.clear_addresses()
            setting_ipv4.props.ignore_auto_routes = False
            setting_ipv4.props.never_default = False
            setting_ipv4.props.ignore_auto_dns = False
            setting_ipv4.props.gateway = None
            setting_ipv4.props.route_table = Route.USE_DEFAULT_ROUTE_TABLE
            setting_ipv4.props.route_metric = Route.USE_DEFAULT_METRIC
            setting_ipv4.clear_routes()
            setting_ipv4.clear_routing_rules()
            setting_ipv4.clear_dns()
            setting_ipv4.clear_dns_searches()
            setting_ipv4.props.dns_priority = nm_dns.DEFAULT_DNS_PRIORITY

    if not setting_ipv4:
        setting_ipv4 = NM.SettingIP4Config.new()

    setting_ipv4.props.dhcp_client_id = "mac"
    setting_ipv4.props.method = NM.SETTING_IP4_CONFIG_METHOD_DISABLED
    if config and config.get(InterfaceIPv4.ENABLED):
        if config.get(InterfaceIPv4.DHCP):
            setting_ipv4.props.method = NM.SETTING_IP4_CONFIG_METHOD_AUTO
            setting_ipv4.props.ignore_auto_routes = not config.get(
                InterfaceIPv4.AUTO_ROUTES, True
            )
            setting_ipv4.props.never_default = not config.get(
                InterfaceIPv4.AUTO_GATEWAY, True
            )
            setting_ipv4.props.ignore_auto_dns = not config.get(
                InterfaceIPv4.AUTO_DNS, True
            )
            setting_ipv4.props.route_table = config.get(
                InterfaceIPv4.AUTO_ROUTE_TABLE_ID,
                Route.USE_DEFAULT_ROUTE_TABLE,
            )
            setting_ipv4.props.dhcp_client_id = config.get(
                InterfaceIPv4.DHCP_CLIENT_ID, None
            )
            # NetworkManager will remove the virtual interfaces like bridges
            # when the DHCP timeout expired, set it to the maximum value to
            # make this unlikely.
            setting_ipv4.props.dhcp_timeout = INT32_MAX
        elif config.get(InterfaceIPv4.ADDRESS):
            setting_ipv4.props.method = NM.SETTING_IP4_CONFIG_METHOD_MANUAL
            _add_addresses(setting_ipv4, config[InterfaceIPv4.ADDRESS])
        nm_route.add_routes(
            setting_ipv4, config.get(BaseIface.ROUTES_METADATA, [])
        )
        nm_dns.add_dns(setting_ipv4, config.get(BaseIface.DNS_METADATA, {}))
        nm_route.add_route_rules(
            setting_ipv4,
            socket.AF_INET,
            config.get(BaseIface.ROUTE_RULES_METADATA, []),
        )
    return setting_ipv4


def _add_addresses(setting_ipv4, addresses):
    for address in addresses:
        naddr = NM.IPAddress.new(
            socket.AF_INET,
            address[InterfaceIPv4.ADDRESS_IP],
            address[InterfaceIPv4.ADDRESS_PREFIX_LENGTH],
        )
        setting_ipv4.add_address(naddr)


def get_info(active_connection, applied_config):
    """
    Provide information regarding:
        * Enable status
        * DHCP status
    """
    if active_connection is None or applied_config is None:
        # Neither unmanaged or not active, let nispor determine its state
        return {}

    info = {InterfaceIPv4.ENABLED: False, InterfaceIPv4.DHCP: False}
    ip_profile = (
        applied_config.get_setting_ip4_config() if applied_config else None
    )
    if ip_profile:
        method = ip_profile.get_method()
        if method == NM.SETTING_IP4_CONFIG_METHOD_DISABLED:
            info[InterfaceIPv4.ENABLED] = False
        else:
            info[InterfaceIPv4.ENABLED] = True
            if method == NM.SETTING_IP4_CONFIG_METHOD_AUTO:
                info[InterfaceIPv4.DHCP] = True
                props = ip_profile.props
                info[InterfaceIPv4.AUTO_ROUTES] = not props.ignore_auto_routes
                info[InterfaceIPv4.AUTO_GATEWAY] = not props.never_default
                info[InterfaceIPv4.AUTO_DNS] = not props.ignore_auto_dns
                info[InterfaceIPv4.AUTO_ROUTE_TABLE_ID] = props.route_table
                if props.dhcp_client_id:
                    info[InterfaceIPv4.DHCP_CLIENT_ID] = props.dhcp_client_id

    return info


def get_ip_profile(active_connection):
    """
    Get NMSettingIP4Config from NMActiveConnection.
    For any error, return None.
    """
    remote_conn = active_connection.get_connection()
    if remote_conn:
        return remote_conn.get_setting_ip4_config()
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
        return ip_profile.get_method() == NM.SETTING_IP4_CONFIG_METHOD_AUTO
    return False
