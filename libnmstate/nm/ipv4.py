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

from . import nmclient
from libnmstate.nm import dns as nm_dns
from libnmstate.nm import route as nm_route
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import Route


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
        setting_ipv4 = nmclient.NM.SettingIP4Config.new()

    setting_ipv4.props.dhcp_client_id = "mac"
    setting_ipv4.props.method = nmclient.NM.SETTING_IP4_CONFIG_METHOD_DISABLED
    if config and config.get(InterfaceIPv4.ENABLED):
        if config.get(InterfaceIPv4.DHCP):
            setting_ipv4.props.method = (
                nmclient.NM.SETTING_IP4_CONFIG_METHOD_AUTO
            )
            setting_ipv4.props.ignore_auto_routes = not config.get(
                InterfaceIPv4.AUTO_ROUTES, True
            )
            setting_ipv4.props.never_default = not config.get(
                InterfaceIPv4.AUTO_GATEWAY, True
            )
            setting_ipv4.props.ignore_auto_dns = not config.get(
                InterfaceIPv4.AUTO_DNS, True
            )
        elif config.get(InterfaceIPv4.ADDRESS):
            setting_ipv4.props.method = (
                nmclient.NM.SETTING_IP4_CONFIG_METHOD_MANUAL
            )
            _add_addresses(setting_ipv4, config[InterfaceIPv4.ADDRESS])
        nm_route.add_routes(
            setting_ipv4, config.get(nm_route.ROUTE_METADATA, [])
        )
        nm_dns.add_dns(setting_ipv4, config.get(nm_dns.DNS_METADATA, {}))
        nm_route.add_route_rules(
            setting_ipv4,
            socket.AF_INET,
            config.get(nm_route.ROUTE_RULES_METADATA, []),
        )
    return setting_ipv4


def _add_addresses(setting_ipv4, addresses):
    for address in addresses:
        naddr = nmclient.NM.IPAddress.new(
            socket.AF_INET,
            address[InterfaceIPv4.ADDRESS_IP],
            address[InterfaceIPv4.ADDRESS_PREFIX_LENGTH],
        )
        setting_ipv4.add_address(naddr)


def get_info(active_connection):
    """
    Provides the current active values for an active connection.
    It includes not only the configured values, but the consequences of the
    configuration (as in the case of ipv4.method=auto, where the address is
    not explicitly defined).
    """
    info = {InterfaceIPv4.ENABLED: False}
    if active_connection is None:
        return info

    ip_profile = get_ip_profile(active_connection)
    if ip_profile:
        info[InterfaceIPv4.DHCP] = ip_profile.get_method() == (
            nmclient.NM.SETTING_IP4_CONFIG_METHOD_AUTO
        )
        props = ip_profile.props
        if info["dhcp"]:
            info[InterfaceIPv4.AUTO_ROUTES] = not props.ignore_auto_routes
            info[InterfaceIPv4.AUTO_GATEWAY] = not props.never_default
            info[InterfaceIPv4.AUTO_DNS] = not props.ignore_auto_dns
            info[InterfaceIPv4.ENABLED] = True
            info[InterfaceIPv4.ADDRESS] = []
    else:
        info[InterfaceIPv4.DHCP] = False

    ip4config = active_connection.get_ip4_config()
    if ip4config is None:
        if not info[InterfaceIPv4.DHCP]:
            del info[InterfaceIPv4.DHCP]
        return info

    addresses = [
        {
            InterfaceIPv4.ADDRESS_IP: address.get_address(),
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: int(address.get_prefix()),
        }
        for address in ip4config.get_addresses()
    ]
    if not addresses:
        return info

    info[InterfaceIPv4.ENABLED] = True
    info[InterfaceIPv4.ADDRESS] = addresses
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


def get_route_running():
    return nm_route.get_running(_acs_and_ip_cfgs(nmclient.client()))


def get_route_config():
    return nm_route.get_config(acs_and_ip_profiles(nmclient.client()))


def _acs_and_ip_cfgs(client):
    for ac in client.get_active_connections():
        ip_cfg = ac.get_ip4_config()
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
        return ip_profile.get_method() == (
            nmclient.NM.SETTING_IP4_CONFIG_METHOD_AUTO
        )
    return False


def get_routing_rule_config():
    return nm_route.get_routing_rule_config(
        acs_and_ip_profiles(nmclient.client())
    )
