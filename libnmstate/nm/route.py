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
import socket

from libnmstate import iplib
from libnmstate.nm import nmclient
from libnmstate.nm import ipv4 as nm_ipv4
from libnmstate.nm import ipv6 as nm_ipv6

IPV4_DEFAULT_GATEWAY_NETWORK = '0.0.0.0/0'
IPV6_DEFAULT_GATEWAY_NETWORK = '::/0'
MAIN_ROUTE_TABLE = 'main'
MAIN_ROUTE_TABLE_INT = 0
IPV6_DEFAULT_ROUTE_METRIC = 1024
IPV6_KERNEL_AUTO_MULTICAST_NETWORK = 'ff00::/8'


def _is_ipv6(ip_cfg):
    return ip_cfg.get_family() == socket.AF_INET6


def _should_skip(dst, skips):
    '''
    Check whether specified route destination should be skipped for unicast
    routing table.
    Meeting any Any of these condition will return True:
        * Is for LAN switch(destination network is a subnet or equal to
          interface network)
        * Is multicast network.
        * Is link-local network.
    '''
    for network in skips:
        if iplib.is_subnet_of(dst, network):
            return True
    return False


def _get_route_table(active_connection, ip_cfg):
    conn = active_connection.get_connection()
    table = MAIN_ROUTE_TABLE
    if _is_ipv6(ip_cfg):
        ip_cfg = conn.get_setting_ip6_config()
    else:
        ip_cfg = conn.get_setting_ip4_config()
    if ip_cfg:
        table = ip_cfg.props.route_table

    if table == MAIN_ROUTE_TABLE_INT:
        return MAIN_ROUTE_TABLE
    else:
        return table


def get_info():
    info = {'ipv4': [], 'ipv6': []}
    client = nmclient.client()
    for active_connection in client.get_active_connections():
        if active_connection is None:
            continue
        ip4_cfg = active_connection.get_ip4_config()
        ip6_cfg = active_connection.get_ip6_config()
        if not ip4_cfg and not ip6_cfg:
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
            raise MissingIfaceNameError(
                'Got connection {} has not interface name'.format(
                    active_connection.get_id()))

        if ip4_cfg:
            skip_networks4 = list('{}/{}'.format(addr.get_address(),
                                                 addr.get_prefix())
                                  for addr in ip4_cfg.get_addresses())
            skip_networks4.append(iplib.IPV4_LINK_LOCAL_NETWORK)
        else:
            skip_networks4 = []

        if ip6_cfg:
            skip_networks6 = list('{}/{}'.format(addr.get_address(),
                                                 addr.get_prefix())
                                  for addr in ip6_cfg.get_addresses())
            skip_networks6.append(iplib.IPV6_LINK_LOCAL_NETWORK)
        else:
            skip_networks6 = []

        static_routes4 = []
        ip4_profile = nm_ipv4.get_ip_profile(active_connection)
        if ip4_profile:
            for route in ip4_profile.props.routes:
                static_routes4.append(
                    '{ip}/{prefix}'.format(
                        ip=route.get_dest(), prefix=route.get_prefix()))

        static_routes6 = []
        ip6_profile = nm_ipv6.get_ip_profile(active_connection)
        if ip6_profile:
            for route in ip6_profile.props.routes:
                static_routes6.append(
                    '{ip}/{prefix}'.format(
                        ip=route.get_dest(), prefix=route.get_prefix()))

        for ip_cfg in (ip4_cfg, ip6_cfg):
            if not ip_cfg:
                continue
            route_table = _get_route_table(active_connection, ip_cfg)
            for route in ip_cfg.get_routes():
                dst = '{ip}/{prefix}'.format(
                    ip=route.get_dest(), prefix=route.get_prefix())
                if dst == IPV6_KERNEL_AUTO_MULTICAST_NETWORK:
                    continue

                route_type = 'static'
                if _is_ipv6(ip_cfg):
                    if _should_skip(dst, skip_networks6):
                        continue
                    if active_connection.get_dhcp6_config() and \
                       dst not in static_routes6:
                        route_type = 'auto'
                else:
                    if _should_skip(dst, skip_networks4):
                        continue
                    if active_connection.get_dhcp4_config() and \
                       dst not in static_routes4:
                        route_type = 'auto'

                next_hop = route.get_next_hop()
                if not next_hop:
                    next_hop = ''
                metric = int(route.get_metric())
                if metric == 0 and _is_ipv6(ip_cfg):
                    metric = IPV6_DEFAULT_ROUTE_METRIC

                route_entry = {
                    'route-type': route_type,
                    'iface': iface_name,
                    'route-table': route_table,
                    'destination': dst,
                    'next-hop': next_hop,
                    'metric': metric,
                }
                if _is_ipv6(ip_cfg):
                    info['ipv6'].append(route_entry)
                else:
                    info['ipv4'].append(route_entry)

    if info == {'ipv4': [], 'ipv6': []}:
        return {}
    return info


def set_routes(ip_setting, routes):
    ip_setting.clear_routes()
    ip_setting.props.gateway = None
    if not routes:
        return
    if not ip_setting.props.addresses:
        # Need at least 1 static address to set routes.
        return
    if routes[0]['route-table'] != MAIN_ROUTE_TABLE:
        ip_setting.props.route_table = int(routes[0]['route-table'])
    else:
        ip_setting.props.route_table = MAIN_ROUTE_TABLE_INT
    for route in routes:
        if route['route-type'] != 'static':
            continue
        if route['destination'] == IPV4_DEFAULT_GATEWAY_NETWORK or \
           route['destination'] == IPV6_DEFAULT_GATEWAY_NETWORK:
            ip_setting.props.gateway = route['next-hop']
            continue
        if type(ip_setting) == nmclient.NM.SettingIP4Config:
            family = socket.AF_INET
        else:
            family = socket.AF_INET6
        dst, prefix = route['destination'].split('/')
        rt = nmclient.NM.IPRoute.new(
            family,
            dst,
            int(prefix),
            route['next-hop'],
            route['metric'])
        ip_setting.add_route(rt)


class MissingIfaceNameError(Exception):
    pass
