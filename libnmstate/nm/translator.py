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


IFACE_TYPE_UNKNOWN = 'unknown'


class ApiIfaceAdminState(object):
    DOWN = 'down'
    UP = 'up'


class Api2Nm(object):
    _iface_types_map = None

    @staticmethod
    def get_iface_type(name):
        return Api2Nm.get_iface_type_map().get(name, IFACE_TYPE_UNKNOWN)

    @staticmethod
    def get_iface_type_map():
        if Api2Nm._iface_types_map is None:
            Api2Nm._iface_types_map = {
                'ethernet': nmclient.NM.SETTING_WIRED_SETTING_NAME,
                'bond': nmclient.NM.SETTING_BOND_SETTING_NAME,
                'dummy': nmclient.NM.SETTING_DUMMY_SETTING_NAME,
            }
        return Api2Nm._iface_types_map

    @staticmethod
    def get_bond_options(bond_conf):
        # Is the mode a must config parameter?
        bond_opts = {'mode': bond_conf['mode']}
        bond_opts.update(bond_conf.get('options', {}))
        return bond_opts


class Nm2Api(object):
    _iface_types_map = None

    @staticmethod
    def get_iface_type(name):
        if Nm2Api._iface_types_map is None:
            Nm2Api._iface_types_map = Nm2Api._swap_dict_keyval(
                Api2Nm.get_iface_type_map())
        return Nm2Api._iface_types_map.get(name, IFACE_TYPE_UNKNOWN)

    @staticmethod
    def get_iface_admin_state(state_name):
        if state_name == nmclient.NM.DeviceState.ACTIVATED:
            return ApiIfaceAdminState.UP
        return ApiIfaceAdminState.DOWN

    @staticmethod
    def _swap_dict_keyval(dictionary):
        return {val: key for key, val in six.viewitems(dictionary)}
