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

UP = 1
DOWN = 0

NM_DEVICE_TYPE_GENERIC = 14


class MockNmConnection(object):
    def get_ip4_config(self):
        return None

    def get_connection(self):
        return MockNmConnection()


class MockNmDevice(object):
    def __init__(self, devstate=DOWN, active_connection=MockNmConnection(),
                 iface="lo"):
        self._devstate = devstate
        self._active_connection = active_connection
        self._iface = iface

    def get_active_connection(self):
        return self._active_connection

    def get_device_type(self):
        return NM_DEVICE_TYPE_GENERIC

    def get_iface(self):
        return self._iface

    def get_state(self):
        return self._devstate

    def get_type_description(self):
        return 'Generic device'
