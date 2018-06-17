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

from libnmstate import nm
from libnmstate import nmclient
from libnmstate import validator


def show():
    report = {'interfaces': interfaces()}
    validator.verify(report)
    return report


def interfaces():
    info = []
    for dev in devices():
        iface_info = {
            'name': dev['name'],
            'type': dev['type'],
            'state': dev['state'],
        }
        _ifaceinfo_bond(dev, iface_info)

        info.append(iface_info)

    return info


def devices():
    devlist = []
    for dev in nm.device.list_devices():
        devinfo = _devinfo_common(dev)
        devinfo.update(_devinfo_bond(dev, devinfo))

        devlist.append(devinfo)

    return devlist


def _ifaceinfo_bond(dev, iface_info):
    # TODO: What about unmanaged devices?
    if iface_info['type'] == 'bond' and 'link-aggregation' in dev:
        iface_info['link-aggregation'] = dev['link-aggregation']


def _devinfo_common(dev):
    type_name = dev.get_type_description()
    if type_name != 'ethernet':
        type_name = nm.translator.nm2api_iface_type(type_name)
    return {
        'name': dev.get_iface(),
        'type_id': dev.get_device_type(),
        'type': type_name,
        'state': nm.translator.nm2api_iface_admin_state(dev.get_state()),
    }


def _devinfo_bond(dev, devinfo):
    if devinfo['type_id'] == nmclient.NM.DeviceType.BOND:
        bond_options = nm.bond.get_options(dev)
        if bond_options:
            bond_mode = bond_options['mode']
            del bond_options['mode']
            return {
                'link-aggregation':
                    {
                        'mode': bond_mode,
                        'slaves': [slave.props.interface
                                   for slave in nm.bond.get_slaves(dev)],
                        'options': bond_options
                    }
            }
    return {}
