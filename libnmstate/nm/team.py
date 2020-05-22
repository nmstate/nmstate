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

import copy
import json

from libnmstate.schema import Interface
from libnmstate.schema import Team

from .common import NM

TEAMD_JSON_DEVICE = "device"
TEAMD_JSON_PORTS = "ports"


def has_team_capability(nm_client):
    return NM.Capability.TEAM in nm_client.get_capabilities()


def create_setting(iface_state, base_con_profile):
    team_setting = None
    team_config = iface_state.get(Team.CONFIG_SUBTREE)

    if not team_config:
        return None

    if base_con_profile:
        team_setting = base_con_profile.get_setting_duplicate(
            NM.SETTING_TEAM_SETTING_NAME
        )

    if not team_setting:
        team_setting = NM.SettingTeam.new()

    teamd_config = _convert_team_config_to_teamd_format(
        team_config, iface_state[Interface.NAME]
    )

    team_setting.props.config = json.dumps(teamd_config)

    return team_setting


def _convert_team_config_to_teamd_format(team_config, ifname):
    team_config = copy.deepcopy(team_config)
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
    Provide the current active teamd values for an interface. Please note that
    these values might be outdated due to the bug below.
    Ref: https://bugzilla.redhat.com/1792232
    """
    info = {}

    if device.get_device_type() == NM.DeviceType.TEAM:
        teamd_json = device.get_config()
        if teamd_json:
            teamd_config = json.loads(teamd_json)
            slave_names = [dev.get_iface() for dev in device.get_slaves()]
            info[Team.CONFIG_SUBTREE] = {
                Team.PORT_SUBTREE: [
                    {Team.Port.NAME: n} for n in sorted(slave_names)
                ],
            }
            runner = _get_runner_name(teamd_config)
            if runner:
                info[Team.CONFIG_SUBTREE][Team.RUNNER_SUBTREE] = {
                    Team.Runner.NAME: runner
                }
    return info


def _get_runner_name(teamd_config):
    return teamd_config.get("runner", {}).get("name")
