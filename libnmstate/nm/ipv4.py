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

from . import nmclient


def create_setting(config, base_con_profile):
    setting_ipv4 = None
    if base_con_profile and config and config.get('enabled'):
        setting_ipv4 = base_con_profile.get_setting_ip4_config()
        if setting_ipv4:
            setting_ipv4 = setting_ipv4.duplicate()
            setting_ipv4.clear_addresses()

    if not setting_ipv4:
        setting_ipv4 = nmclient.NM.SettingIP4Config.new()

    setting_ipv4.props.method = (
        nmclient.NM.SETTING_IP4_CONFIG_METHOD_DISABLED)
    if config and config.get('enabled'):
        if config.get('dhcp'):
            setting_ipv4.props.method = (
                nmclient.NM.SETTING_IP4_CONFIG_METHOD_AUTO)
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
