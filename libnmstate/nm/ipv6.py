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
import socket

from libnmstate import iplib
from libnmstate.error import NmstateNotImplementedError
from libnmstate.nm import nmclient
from libnmstate.nm import route as nm_route
from libnmstate.schema import Route


IPV6_DEFAULT_ROUTE_METRIC = 1024


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


def _set_dynamic(setting_ip, is_dhcp, is_autoconf):
    if not is_dhcp and is_autoconf:
        raise NmstateNotImplementedError(
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


def get_route_running():
    return nm_route.get_running(_acs_and_ip_cfgs(nmclient.client()))


def get_route_config():
    routes = nm_route.get_config(_acs_and_ip_profiles(nmclient.client()))
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


def _acs_and_ip_profiles(client):
    for ac in client.get_active_connections():
        ip_profile = get_ip_profile(ac)
        if not ip_profile:
            continue
        yield ac, ip_profile
