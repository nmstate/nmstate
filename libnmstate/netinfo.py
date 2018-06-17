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
from libnmstate import validator


def show():
    report = {'interfaces': interfaces()}
    validator.verify(report)
    return report


def interfaces():
    info = []
    for dev in nm.device.list_devices():
        devinfo = nm.device.get_device_common_info(dev)
        type_id = devinfo['type_id']
        iface_info = nm.translator.Nm2Api.get_common_device_info(devinfo)

        act_con = nm.connection.get_device_active_connection(dev)
        iface_info['ipv4'] = nm.ipv4.get_info(act_con)

        if nm.bond.is_bond_type_id(type_id):
            bondinfo = nm.bond.get_bond_info(dev)
            iface_info.update(_ifaceinfo_bond(bondinfo))

        info.append(iface_info)

    return info


def _ifaceinfo_bond(devinfo):
    # TODO: What about unmanaged devices?
    bondinfo = nm.translator.Nm2Api.get_bond_info(devinfo)
    if 'link-aggregation' in bondinfo:
        return bondinfo
    return {}
