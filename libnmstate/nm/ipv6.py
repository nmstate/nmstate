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

from libnmstate.nm import nmclient
from libnmstate import iplib

IPV6_DEFAULT_GATEWAY_NETWORK = '::/0'
MAIN_ROUTE_TABLE = 'main'
MAIN_ROUTE_TABLE_INT = 0
IPV6_DEFAULT_ROUTE_METRIC = 1024
IPV6_KERNEL_AUTO_MULTICAST_NETWORK = 'ff00::/8'



def get_info(active_connection):
    info = {'enabled': False}
    if active_connection is None:
        return info

    info['dhcp'] = False
    info['autoconf'] = False

    ip_profile = get_ip_profile(active_connection)
    if ip_profile:
        method = ip_profile.get_method()
        if method == nmclient.NM.SETTING_IP6_CONFIG_METHOD_AUTO:
            info['dhcp'] = True
            info['autoconf'] = True
        elif method == nmclient.NM.SETTING_IP6_CONFIG_METHOD_DHCP:
            info['dhcp'] = True
            info['autoconf'] = False

        if info['dhcp'] or info['autoconf']:
            info['auto-routes'] = not ip_profile.props.ignore_auto_routes
            info['auto-gateway'] = not ip_profile.props.never_default
            info['auto-dns'] = not ip_profile.props.ignore_auto_dns

    ipconfig = active_connection.get_ip6_config()
    if ipconfig is None:
        # When DHCP is enable, it might be possible, the active_connection does
        # not got IP address yet. In that case, we still mark
        # info['enabled'] as True.
        if info['dhcp'] or info['autoconf']:
            info['enabled'] = True
            info['address'] = []
        else:
            del info['dhcp']
            del info['autoconf']
        return info

    addresses = [
        {
            'ip': address.get_address(),
            'prefix-length': int(address.get_prefix())
        }
        for address in ipconfig.get_addresses()
    ]
    if not addresses:
        return info

    info['enabled'] = True
    info['address'] = addresses
    return info


def create_setting(config, base_con_profile):
    setting_ip = None
    if base_con_profile and config and config.get('enabled'):
        setting_ip = base_con_profile.get_setting_ip6_config()
        if setting_ip:
            setting_ip = setting_ip.duplicate()
            setting_ip.clear_addresses()
            setting_ip.props.ignore_auto_routes = False
            setting_ip.props.never_default = False
            setting_ip.props.ignore_auto_dns = False

    if not setting_ip:
        setting_ip = nmclient.NM.SettingIP6Config.new()

    if not config or not config.get('enabled'):
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_IGNORE)
        return setting_ip

    is_dhcp = config.get('dhcp', False)
    is_autoconf = config.get('autoconf', False)
    ip_addresses = config.get('address', ())

    if is_dhcp or is_autoconf:
        _set_dynamic(setting_ip, is_dhcp, is_autoconf)
        setting_ip.props.ignore_auto_routes = (
            not config.get('auto-routes', True))
        setting_ip.props.never_default = (
            not config.get('auto-gateway', True))
        setting_ip.props.ignore_auto_dns = (
            not config.get('auto-dns', True))
    elif ip_addresses:
        _set_static(setting_ip, ip_addresses)
    else:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL)

    return setting_ip


class NoSupportDynamicIPv6OptionError(Exception):
    pass


def _set_dynamic(setting_ip, is_dhcp, is_autoconf):
    if not is_dhcp and is_autoconf:
        raise NoSupportDynamicIPv6OptionError(
            'Autoconf without DHCP is not supported yet')

    if is_dhcp and is_autoconf:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_AUTO)
    elif is_dhcp and not is_autoconf:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_DHCP)


def _set_static(setting_ip, ip_addresses):
    for address in ip_addresses:
        if iplib.is_ipv6_link_local_addr(address['ip'],
                                         address['prefix-length']):
            logging.warning('IPv6 link local address '
                            '{a[ip]}/{a[prefix-length]} is ignored '
                            'when applying desired state'
                            .format(a=address))
        else:
            naddr = nmclient.NM.IPAddress.new(socket.AF_INET6,
                                              address['ip'],
                                              address['prefix-length'])
            setting_ip.add_address(naddr)

    if setting_ip.props.addresses:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_MANUAL)
    else:
        setting_ip.props.method = (
            nmclient.NM.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL)


def get_ip_profile(active_connection):
    """
    Get NMSettingIP6Config from NMActiveConnection.
    For any error, return None.
    """
    remote_conn = active_connection.get_connection()
    if remote_conn:
        return remote_conn.get_setting_ip6_config()
    return None


def get_route_info():
    ret = []
    client = nmclient.client()
    for active_connection in client.get_active_connections():
        if active_connection is None:
            continue
        ip_cfg = active_connection.get_ip6_config()
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
        skip_networks.append(iplib.IPV6_LINK_LOCAL_NETWORK)

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
            if dst == IPV6_KERNEL_AUTO_MULTICAST_NETWORK:
                continue
            if _should_skip(dst, skip_networks):
                continue

            route_origin = 'static'
            if _ra_is_enabled(ip_profile) and dst not in static_routes:
                route_origin = 'router-advertisement'

            next_hop = route.get_next_hop()
            if not next_hop:
                next_hop = ''
            metric = int(route.get_metric())
            if metric == 0:
                metric = IPV6_DEFAULT_ROUTE_METRIC

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
    ip_cfg = conn.get_setting_ip6_config()
    table_id = ip_cfg.props.route_table if ip_cfg else MAIN_ROUTE_TABLE_INT
    if table_id == MAIN_ROUTE_TABLE_INT:
        return iplib.get_route_table_id(MAIN_ROUTE_TABLE)
    return table_id


def _ra_is_enabled(ip_profile):
    """
    Return True if IPv6 router advertisement is enabled.
    """
    if ip_profile and \
       ip_profile.get_method() == nmclient.NM.SETTING_IP6_CONFIG_METHOD_AUTO:
        return True
    return False
