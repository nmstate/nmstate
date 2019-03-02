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
""" Use a Network Manager User Setting to store and retrieve information that
does not fit somewhere else such as an interface's description.

https://lazka.github.io/pgi-docs/#NM-1.0/classes/SettingUser.html
"""

from libnmstate.error import NmstateValueError
from libnmstate.nm import connection as nm_connection
from libnmstate.nm import nmclient

NMSTATE_DESCRIPTION = "nmstate.interface.description"


def create_setting(iface_state, base_con_profile):
    description = iface_state.get('description')

    if not description:
        return None

    if not nmclient.NM.SettingUser.check_val(description):
        raise NmstateValueError('Invalid description')

    user_setting = None
    if base_con_profile:
        user_setting = base_con_profile.get_setting_by_name(
            nmclient.NM.SETTING_USER_SETTING_NAME)
        if user_setting:
            user_setting = user_setting.duplicate()

    if not user_setting:
        user_setting = nmclient.NM.SettingUser.new()

    user_setting.set_data(NMSTATE_DESCRIPTION, description)
    return user_setting


def get_info(device):
    """
    Get description from user settings for a connection
    """
    info = {}

    connection = nm_connection.ConnectionProfile()
    connection.import_by_device(device)
    if not connection.profile:
        return info

    try:
        user_setting = connection.profile.get_setting_by_name(
            nmclient.NM.SETTING_USER_SETTING_NAME)
        description = user_setting.get_data(NMSTATE_DESCRIPTION)
        if description:
            info['description'] = description
    except AttributeError:
        pass

    return info
