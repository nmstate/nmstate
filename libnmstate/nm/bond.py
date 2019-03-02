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

import six

from . import connection
from . import nmclient
from libnmstate.error import NmstateValueError


BOND_TYPE = 'bond'


def create_setting(options):
    bond_setting = nmclient.NM.SettingBond.new()
    for option_name, option_value in six.viewitems(options):
        success = bond_setting.add_option(option_name, option_value)
        if not success:
            raise NmstateValueError(
                'Invalid bond option: \{}\=\'{}\''.format(
                    option_name, option_value))

    return bond_setting


def is_bond_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.BOND


def get_bond_info(nm_device):
    return {
        'slaves': get_slaves(nm_device),
        'options': get_options(nm_device)
    }


def get_options(nm_device):
    con = connection.ConnectionProfile()
    con.import_by_device(nm_device)
    if con.profile:
        bond_settings = con.profile.get_setting_bond()
        return bond_settings.props.options
    return {}


def get_slaves(nm_device):
    return nm_device.get_slaves()
