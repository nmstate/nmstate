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

from libnmstate.nm import nmclient
from libnmstate import iplib


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
