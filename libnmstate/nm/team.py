#
# Copyright (c) 2019 Red Hat, Inc.
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

import json

from libnmstate.nm import connection as nm_connection
from libnmstate.nm import nmclient
from libnmstate.schema import Interface
from libnmstate.schema import Team


TEAMD_JSON_DEVICE = "device"


def create_setting(iface_state, base_con_profile):
    team_setting = None
    team_config = iface_state.get(Team.CONFIG_SUBTREE)

    if not team_config:
        return None

    if base_con_profile:
        team_setting = base_con_profile.get_setting_duplicate(
            nmclient.NM.SETTING_TEAM_SETTING_NAME
        )

    if not team_setting:
        team_setting = nmclient.NM.SettingTeam.new()

    teamd_config = _convert_team_config_to_teamd_format(
        team_config, iface_state[Interface.NAME]
    )

    team_setting.props.config = json.dumps(teamd_config)

    return team_setting


def _convert_team_config_to_teamd_format(team_config, ifname):
    team_config[TEAMD_JSON_DEVICE] = ifname

    team_ports = team_config.get(Team.PORT_SUBTREE, ())
    team_ports_formatted = {
        port[Team.Port.NAME]: _dict_key_filter(port, Team.Port.NAME)
        for port in team_ports
    }
    team_config[Team.PORT_SUBTREE] = team_ports_formatted

    return team_config


def _dict_key_filter(dict_to_filter, key):
    return dict(filter(lambda elem: elem[0] == key, dict_to_filter.items()))


def get_info(device):
    """
    Provide the current active teamd values for an interface.
    Ref: https://bugzilla.redhat.com/1792232
    """
    info = {}

    connection = nm_connection.ConnectionProfile()
    connection.import_by_device(device)
    if not connection.profile:
        return info

    team_setting = connection.profile.get_setting_by_name(
        nmclient.NM.SETTING_TEAM_SETTING_NAME
    )

    if team_setting:
        teamd_json = team_setting.get_config()
        if teamd_json:
            teamd_config = json.loads(teamd_json)
            team_config = _convert_teamd_config_to_nmstate_config(teamd_config)
            info[Team.CONFIG_SUBTREE] = team_config

    return info


def _convert_teamd_config_to_nmstate_config(team_config):
    team_config.pop("device")
    port_config = team_config.get(Team.PORT_SUBTREE)

    if port_config:
        team_port = _teamd_port_to_nmstate_port(port_config)
        team_config[Team.PORT_SUBTREE] = team_port

    return team_config


def _teamd_port_to_nmstate_port(port_config):
    port_list = []
    for name, port in port_config.items():
        port.update({Team.Port.NAME: name})
        port_list.append(port)

    return port_list
