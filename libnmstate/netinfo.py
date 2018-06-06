#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

from libnmstate import nmclient
from libnmstate import validator


def show():
    report = interfaces()
    validator.verify(report)
    return report


def interfaces():
    return {
        'interfaces': [
            {
                'name': dev['name'],
                'type': dev['type'],
                'state': dev['state'],
                'ip': dev['ip'],
            }
            for dev in devices()
        ]
    }


def devices():
    client = nmclient.client()

    devlist = []
    for device in client.get_devices():
        ip4info = {}
        connection = device.get_active_connection()
        if connection:
            ip4config = connection.get_ip4_config()
            if ip4config:
                ip4info["enabled"] = True
                addresslist = []

                addresses = ip4config.get_addresses()
                for address in addresses:
                    addressinfo = {"ip": address.get_address(),
                                   "prefix-length": address.get_prefix()}
                    addresslist.append(addressinfo)
                if addresslist:
                    ip4info["addresses"] = addresslist
            else:
                ip4info["enabled"] = False
        else:
            ip4info["enabled"] = False

        devinfo = {
            'name': device.get_iface(),
            'type_id': device.get_device_type(),
            'type': resolve_nm_dev_type(device.get_type_description()),
            'state': resolve_nm_dev_state(device.get_state()),
            'ip': ip4info,
        }
        devlist.append(devinfo)

    return devlist


def resolve_nm_dev_state(nm_state):
    if nm_state == nmclient.NM.DeviceState.ACTIVATED:
        return 'up'
    return 'down'


def resolve_nm_dev_type(nm_type):
    if nm_type != 'ethernet':
        return 'unknown'
    return nm_type
