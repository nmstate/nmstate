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

from libnmstate import nmclient


def create_setting(config):
    setting_ipv4 = nmclient.NM.SettingIP4Config.new()
    if config and config.get('enabled') and config.get('addresses'):
        setting_ipv4.props.method = (
            nmclient.NM.SETTING_IP4_CONFIG_METHOD_MANUAL)
        _add_addresses(setting_ipv4, config['addresses'])
    else:
        setting_ipv4.props.method = (
            nmclient.NM.SETTING_IP4_CONFIG_METHOD_DISABLED)
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

    ip4config = active_connection.get_ip4_config()
    if ip4config is None:
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
    info['addresses'] = addresses
    return info
