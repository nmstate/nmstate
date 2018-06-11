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

import six

from libnmstate import nmclient

from . import connection


def create_setting(options):
    bond_setting = nmclient.NM.SettingBond.new()
    for option_name, option_value in six.viewitems(options):
        success = bond_setting.add_option(option_name, option_value)
        if not success:
            raise InvalidBondOptionError(option_name, option_value)
    return bond_setting


def get_options(nm_device):
    con = connection.get_device_connection(nm_device)
    if con:
        bond_settings = con.get_setting_bond()
        return bond_settings.props.options
    return {}


def get_slaves(nm_device):
    return nm_device.get_slaves()


class InvalidBondOptionError(Exception):
    pass
