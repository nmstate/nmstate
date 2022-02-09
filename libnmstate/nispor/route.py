#
# Copyright (c) 2020-2022 Red Hat, Inc.
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

from copy import deepcopy

from libnmstate.schema import Route


IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"

IPV4_EMPTY_NEXT_HOP_ADDRESS = "0.0.0.0"
IPV6_EMPTY_NEXT_HOP_ADDRESS = "::"

LOCAL_ROUTE_TABLE = 255


def nispor_route_state_to_nmstate(np_routes):
    ret = []
    for np_route in np_routes:
        if np_route.oif != "lo" and np_route.table != LOCAL_ROUTE_TABLE:
            ret.extend(_nispor_route_to_nmstate(np_route))
    return ret


def nispor_route_state_to_nmstate_static(np_routes):
    ret = []
    for np_route in np_routes:
        if (
            np_route.oif != "lo"
            and np_route.table != LOCAL_ROUTE_TABLE
            and np_route.scope in ["universe", "link"]
            and np_route.protocol in ["static", "boot"]
        ):
            ret.extend(_nispor_route_to_nmstate(np_route))
    return ret


def _nispor_route_to_nmstate(np_rt):
    if np_rt.dst:
        destination = np_rt.dst
    else:
        destination = (
            IPV6_DEFAULT_GATEWAY_DESTINATION
            if np_rt.address_family == "ipv6"
            else IPV4_DEFAULT_GATEWAY_DESTINATION
        )

    if np_rt.via:
        next_hop = np_rt.via
    elif np_rt.gateway:
        next_hop = np_rt.gateway
    else:
        next_hop = (
            IPV6_EMPTY_NEXT_HOP_ADDRESS
            if np_rt.address_family == "ipv6"
            else IPV4_EMPTY_NEXT_HOP_ADDRESS
        )

    nm_route = {
        Route.TABLE_ID: np_rt.table,
        Route.DESTINATION: destination,
        Route.NEXT_HOP_INTERFACE: np_rt.oif if np_rt.oif else "",
        Route.NEXT_HOP_ADDRESS: next_hop,
        Route.METRIC: np_rt.metric if np_rt.metric else 0,
    }
    np_mp_rts = get_multipath_routes(np_rt)
    if np_mp_rts:
        ret = []
        for np_mp_rt in np_mp_rts:
            nm_route_clone = deepcopy(nm_route)
            nm_route_clone[Route.NEXT_HOP_INTERFACE] = np_mp_rt["iface"]
            nm_route_clone[Route.NEXT_HOP_ADDRESS] = np_mp_rt["via"]
            ret.append(nm_route_clone)
        return ret
    else:
        return [nm_route]


# Instead of bumping nispor dependency version, we just use nispor private
# property temporarily
def get_multipath_routes(np_route):
    return np_route._info.get("multipath")
