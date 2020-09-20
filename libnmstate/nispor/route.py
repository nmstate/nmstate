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

from libnmstate.schema import Route


IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"


def nispor_route_state_to_nmstate(np_routes):
    return [
        _nispor_route_to_nmstate(rt)
        for rt in np_routes
        if rt.scope == "Universe"
    ]


def _nispor_route_to_nmstate(np_rt):
    if np_rt.dst:
        destination = np_rt.dst
    elif np_rt.gateway:
        destination = (
            IPV6_DEFAULT_GATEWAY_DESTINATION
            if np_rt.address_family == "IPv6"
            else IPV4_DEFAULT_GATEWAY_DESTINATION
        )
    else:
        destination = ""

    if np_rt.via:
        next_hop = np_rt.via
    elif np_rt.gateway:
        next_hop = np_rt.gateway
    else:
        next_hop = ""

    return {
        Route.TABLE_ID: np_rt.table,
        Route.DESTINATION: destination,
        Route.NEXT_HOP_INTERFACE: np_rt.oif if np_rt.oif else "",
        Route.NEXT_HOP_ADDRESS: next_hop,
        Route.METRIC: np_rt.metric if np_rt.metric else 0,
    }
