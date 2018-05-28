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
            }
            for dev in devices()
        ]
    }


def devices():
    client = nmclient.client()

    devs = client.get_devices()

    devlist = [
        {
            'name': dev.get_iface(),
            'type_id': dev.get_device_type(),
            'type': resolve_nm_dev_type(dev.get_type_description()),
            'state': resolve_nm_dev_state(dev.get_state()),
        }
        for dev in devs
    ]

    return devlist


def resolve_nm_dev_state(nm_state):
    if nm_state == nmclient.NM.DeviceState.ACTIVATED:
        return 'up'
    return 'unknown'


def resolve_nm_dev_type(nm_type):
    if nm_type != 'ethernet':
        return 'unknown'
    return nm_type
