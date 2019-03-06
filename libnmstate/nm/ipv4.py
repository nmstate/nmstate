#
# Copyright 2018 Red Hat, Inc.
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

import logging
from operator import itemgetter
import socket

from . import nmclient
from libnmstate import iplib

IPV4_DEFAULT_GATEWAY_NETWORK = '0.0.0.0/0'
MAIN_ROUTE_TABLE = 'main'
MAIN_ROUTE_TABLE_INT = 0


def create_setting(config, base_con_profile):
    setting_ipv4 = None
    if base_con_profile and config and config.get('enabled'):
        setting_ipv4 = base_con_profile.get_setting_ip4_config()
        if setting_ipv4:
            setting_ipv4 = setting_ipv4.duplicate()
            setting_ipv4.clear_addresses()
            setting_ipv4.props.ignore_auto_routes = False
            setting_ipv4.props.never_default = False
            setting_ipv4.props.ignore_auto_dns = False

    if not setting_ipv4:
        setting_ipv4 = nmclient.NM.SettingIP4Config.new()

    setting_ipv4.props.method = (
        nmclient.NM.SETTING_IP4_CONFIG_METHOD_DISABLED)
    if config and config.get('enabled'):
        if config.get('dhcp'):
            setting_ipv4.props.method = (
                nmclient.NM.SETTING_IP4_CONFIG_METHOD_AUTO)
            setting_ipv4.props.ignore_auto_routes = (
                not config.get('auto-routes', True))
            setting_ipv4.props.never_default = (
                not config.get('auto-gateway', True))
            setting_ipv4.props.ignore_auto_dns = (
                not config.get('auto-dns', True))
        elif config.get('address'):
            setting_ipv4.props.method = (
                nmclient.NM.SETTING_IP4_CONFIG_METHOD_MANUAL)
            _add_addresses(setting_ipv4, config['address'])
    return setting_ipv4


def _add_addresses(setting_ipv4, addresses):
    for address in addresses:
        naddr = nmclient.NM.IPAddress.new(socket.AF_INET,
                                          address['ip'],
                                          address['prefix-length'])
        setting_ipv4.add_address(naddr)


def get_info(active_connection):
    """
    Provides the current active values for an active connection.
    It includes not only the configured values, but the consequences of the
    configuration (as in the case of ipv4.method=auto, where the address is
    not explicitly defined).
    """
    info = {'enabled': False}
    if active_connection is None:
        return info

    ip_profile = get_ip_profile(active_connection)
    if ip_profile:
        info['dhcp'] = ip_profile.get_method() == (
            nmclient.NM.SETTING_IP4_CONFIG_METHOD_AUTO)
        if info['dhcp']:
            info['auto-routes'] = not ip_profile.props.ignore_auto_routes
            info['auto-gateway'] = not ip_profile.props.never_default
            info['auto-dns'] = not ip_profile.props.ignore_auto_dns
    else:
        info['dhcp'] = False

    ip4config = active_connection.get_ip4_config()
    if ip4config is None:
        # When DHCP is enable, it might be possible, the active_connection does
        # not got IP address yet. In that case, we still mark
        # info['enabled'] as True.
        if info['dhcp']:
            info['enabled'] = True
            info['address'] = []
        else:
            del info['dhcp']
        return info

    addresses = [
        {
            'ip': address.get_address(),
            'prefix-length': int(address.get_prefix())
        }
        for address in ip4config.get_addresses()
    ]
    if not addresses:
        return info

    info['enabled'] = True
    info['address'] = addresses
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


def get_route_info():
    ret = []
    client = nmclient.client()
    for active_connection in client.get_active_connections():
        if active_connection is None:
            continue
        ip_cfg = active_connection.get_ip4_config()
        if not ip_cfg:
            continue

        devs = active_connection.get_devices()
        iface_name = None
        # If we have master device, we use it, else we use first device.
        if hasattr(active_connection, 'master'):
            iface_name = active_connection.master.get_iface()
        else:
            devs = active_connection.get_devices()
            if devs:
                iface_name = devs[0].get_iface()

        if not iface_name:
            logging.warning(
                'Got connection {} has not interface name'.format(
                    active_connection.get_id()))
            continue

        skip_networks = list('{}/{}'.format(addr.get_address(),
                                             addr.get_prefix())
                              for addr in ip_cfg.get_addresses())
        skip_networks.append(iplib.IPV4_LINK_LOCAL_NETWORK)

        static_routes = []
        ip_profile = get_ip_profile(active_connection)
        if ip_profile:
            for route in ip_profile.props.routes:
                static_routes.append(
                    '{ip}/{prefix}'.format(
                        ip=route.get_dest(), prefix=route.get_prefix()))

        table_id = _get_route_table_id(active_connection, ip_cfg)
        for route in ip_cfg.get_routes():
            dst = '{ip}/{prefix}'.format(
                ip=route.get_dest(), prefix=route.get_prefix())
            if _should_skip(dst, skip_networks):
                continue
            route_origin = 'static'
            if active_connection.get_dhcp4_config() and \
               dst not in static_routes:
                route_origin = 'dhcp'

            next_hop = route.get_next_hop()
            if not next_hop:
                next_hop = ''
            metric = int(route.get_metric())
            route_entry = {
                'status': 'up',
                'origin': route_origin,
                'table-id': table_id,
                'table-name': iplib.get_route_table_name(table_id),
                'destination': dst,
                'next-hop-iface': iface_name,
                'next-hop-address': next_hop,
                'metric': metric,
            }
            ret.append(route_entry)
    ret.sort(key=itemgetter('table-id', 'destination'))
    return ret


def _should_skip(dst, skips):
    '''
    Check whether specified route destination should be skipped for unicast
    routing table.
    Meeting any Any of these condition will return True:
        * Is direct route(route for the LAN network)
        * Is link-local network.
    '''
    for network in skips:
        if iplib.is_subnet_of(dst, network):
            return True
    return False


def _get_route_table_id(active_connection, ip_cfg):
    conn = active_connection.get_connection()
    ip_cfg = conn.get_setting_ip4_config()
    table_id = ip_cfg.props.route_table if ip_cfg else MAIN_ROUTE_TABLE_INT
    if table_id == MAIN_ROUTE_TABLE_INT:
        return iplib.get_route_table_id(MAIN_ROUTE_TABLE)
    return table_id
