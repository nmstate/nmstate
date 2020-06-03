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
from libnmstate.route import RouteEntry

from .constants import IPV4_ADDRESS1
from .constants import IPV6_ADDRESS1

IPV4_ROUTE_IFACE_NAME = "ipv4_route_iface"
IPV4_ROUTE_DESITNATION = "198.51.100.0/24"
IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
IPV4_ROUTE_TABLE_ID = 51
IPV6_ROUTE_IFACE_NAME = "ipv6_route_iface"
IPV6_ROUTE_DESITNATION = "2001:db8:a::/64"
IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"
IPV6_ROUTE_TABLE_ID = 52


def gen_ipv4_route():
    return _create_route(
        IPV4_ROUTE_DESITNATION,
        103,
        IPV4_ADDRESS1,
        IPV4_ROUTE_IFACE_NAME,
        IPV4_ROUTE_TABLE_ID,
    )


def gen_ipv6_route():
    return _create_route(
        IPV6_ROUTE_DESITNATION,
        104,
        IPV6_ADDRESS1,
        IPV6_ROUTE_IFACE_NAME,
        IPV6_ROUTE_TABLE_ID,
    )


def gen_ipv4_default_gateway():
    return _create_route(
        IPV4_DEFAULT_GATEWAY_DESTINATION,
        104,
        IPV4_ADDRESS1,
        IPV4_ROUTE_IFACE_NAME,
        52,
    )


def gen_ipv6_default_gateway():
    return _create_route(
        IPV6_DEFAULT_GATEWAY_DESTINATION,
        104,
        IPV6_ADDRESS1,
        IPV6_ROUTE_IFACE_NAME,
        52,
    )


def _create_route(dest, metric, via_addr, via_iface, table_id):
    return RouteEntry(
        {
            Route.DESTINATION: dest,
            Route.METRIC: metric,
            Route.NEXT_HOP_ADDRESS: via_addr,
            Route.NEXT_HOP_INTERFACE: via_iface,
            Route.TABLE_ID: table_id,
        }
    )
