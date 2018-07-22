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
from __future__ import absolute_import

from libnmstate import nm
from libnmstate import validator


def show(include_status_data=False):
    """
    Reports configuration and status data on the system.
    Configuration data is the set of writable data which can change the system
    state.
    Status data is the additional data which is not configuration data,
    including read-only and statistics information.
    When include_status_data is set, both are reported, otherwise only the
    configuration data is reported.
    """
    report = {'interfaces': interfaces()}
    if include_status_data:
        report['capabilities'] = capabilities()

    validator.verify(report)
    return report


def capabilities():
    caps = set()

    if nm.ovs.has_ovs_capability():
        caps.add(nm.ovs.CAPABILITY)

    return list(caps)


def interfaces():
    info = []

    devices_info = [(dev, nm.device.get_device_common_info(dev))
                    for dev in nm.device.list_devices()]

    for dev, devinfo in devices_info:
        type_id = devinfo['type_id']

        iface_info = nm.translator.Nm2Api.get_common_device_info(devinfo)

        act_con = nm.connection.get_device_active_connection(dev)
        iface_info['ipv4'] = nm.ipv4.get_info(act_con)

        if nm.bond.is_bond_type_id(type_id):
            bondinfo = nm.bond.get_bond_info(dev)
            iface_info.update(_ifaceinfo_bond(bondinfo))
        elif nm.ovs.has_ovs_capability():
            if nm.ovs.is_ovs_bridge_type_id(type_id):
                iface_info['bridge'] = nm.ovs.get_ovs_info(dev, devices_info)
            elif nm.ovs.is_ovs_port_type_id(type_id):
                continue

        info.append(iface_info)

    return info


def _ifaceinfo_bond(devinfo):
    # TODO: What about unmanaged devices?
    bondinfo = nm.translator.Nm2Api.get_bond_info(devinfo)
    if 'link-aggregation' in bondinfo:
        return bondinfo
    return {}
