#
# Copyright (c) 2020 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from libnmstate.nm import connection
from libnmstate.nm import device
from libnmstate.nm import ovs


def list_profiles_by_iface_name(iface_name):
    return connection.list_connections_by_ifname(iface_name)


def get_ovs_port_by_slave(iface_name):
    """
    Given an interface name, return the interface name of the OVS port
    it is connected to. In any other case, return None.
    """
    iface_nmdev = device.get_device_by_name(iface_name)
    if iface_nmdev:
        port_nmdev = ovs.get_port_by_slave(iface_nmdev)
        if port_nmdev:
            return port_nmdev.get_iface()
    return None
