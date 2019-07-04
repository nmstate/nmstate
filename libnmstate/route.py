#
# Copyright 2019 Red Hat, Inc.
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

import copy

import libnmstate.nm.ipv4 as nm_ipv4
import libnmstate.nm.ipv6 as nm_ipv6
from libnmstate.schema import Route


class RouteState(object):
    def __init__(self, state_dict=None):
        if state_dict is None:
            state_dict = RouteState._get()
        self._running = state_dict.get(Route.RUNNING)
        self._config = state_dict.get(Route.CONFIG)

    @staticmethod
    def _get():
        return {
            Route.RUNNING: nm_ipv4.get_route_running()
            + nm_ipv6.get_route_running(),
            Route.CONFIG: nm_ipv4.get_route_config()
            + nm_ipv6.get_route_config(),
        }

    def dump(self):
        return {Route.RUNNING: self._running, Route.CONFIG: self._config}

    def merge_config(self, current):
        pass

    def generate_metadata(self, iface_state):
        pass

    def pre_merge_validate(self):
        pass

    def post_merge_validate(self):
        pass

    def verify(self, current):
        pass
