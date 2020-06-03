#
# Copyright (c) 2019-2020 Red Hat, Inc.
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
from unittest import mock

import pytest

from libnmstate import iplib
from libnmstate.error import NmstateNotImplementedError
from libnmstate.nm import ipv4 as nm_ipv4
from libnmstate.nm import ipv6 as nm_ipv6
from libnmstate.nm import connection as nm_connection
from libnmstate.ifaces import BaseIface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import Route

IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"

IPV4_ROUTE1 = {
    Route.DESTINATION: "198.51.100.0/24",
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: "192.0.2.1",
    Route.TABLE_ID: 50,
}

IPV4_ROUTE2 = {
    Route.DESTINATION: "203.0.113.0/24",
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: "192.0.2.2",
    Route.TABLE_ID: 51,
}

IPV6_ROUTE1 = {
    Route.DESTINATION: "2001:db8:a::/64",
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: "2001:db8:1::a",
    Route.TABLE_ID: 50,
}

IPV6_ROUTE2 = {
    Route.DESTINATION: "2001:db8:b::/64",
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: "2001:db8:1::b",
    Route.TABLE_ID: 51,
}

parametrize_ip_ver_routes = pytest.mark.parametrize(
    "nm_ip, routes",
    [
        (nm_ipv4, [IPV4_ROUTE1, IPV4_ROUTE2]),
        (nm_ipv6, [IPV6_ROUTE1, IPV6_ROUTE2]),
    ],
    ids=["ipv4", "ipv6"],
)


@pytest.fixture
def client_mock():
    yield mock.MagicMock()


def _get_test_ipv4_gateways():
    return [
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "192.0.2.1",
            Route.TABLE_ID: 52,
        },
        {
            Route.DESTINATION: "0.0.0.0/0",
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: "192.0.2.2",
            Route.TABLE_ID: 53,
        },
    ]


def _get_test_ipv6_gateways():
    return [
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 103,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::f",
            Route.TABLE_ID: 52,
        },
        {
            Route.DESTINATION: "::/0",
            Route.METRIC: 101,
            Route.NEXT_HOP_ADDRESS: "2001:db8:1::e",
            Route.TABLE_ID: 53,
        },
    ]


parametrize_ip_ver_routes_gw = pytest.mark.parametrize(
    "nm_ip, routes, gateways",
    [
        (nm_ipv4, [IPV4_ROUTE1, IPV4_ROUTE2], _get_test_ipv4_gateways()),
        (nm_ipv6, [IPV6_ROUTE1, IPV6_ROUTE2], _get_test_ipv6_gateways()),
    ],
    ids=["ipv4", "ipv6"],
)


@parametrize_ip_ver_routes
def test_add_multiple_route(nm_ip, routes):
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, BaseIface.ROUTES_METADATA: routes},
        base_con_profile=None,
    )
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == routes


@parametrize_ip_ver_routes
def test_add_duplicate_routes(nm_ip, routes):
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: [routes[0], routes[0]],
        },
        base_con_profile=None,
    )
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == [
        routes[0]
    ]


@parametrize_ip_ver_routes
def test_clear_route(nm_ip, routes, client_mock):
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, BaseIface.ROUTES_METADATA: routes},
        base_con_profile=None,
    )
    con_profile = nm_connection.ConnectionProfile(client_mock)
    con_profile.create([setting_ip])
    new_setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, BaseIface.ROUTES_METADATA: []},
        base_con_profile=con_profile.profile,
    )
    assert not [_nm_route_to_dict(r) for r in new_setting_ip.props.routes]


@parametrize_ip_ver_routes
def test_add_route_without_metric(nm_ip, routes):
    route_with_default_metric = copy.deepcopy(routes[0])
    route_with_default_metric[Route.METRIC] = Route.USE_DEFAULT_METRIC
    route_without_metric = copy.deepcopy(routes[0])
    del route_without_metric[Route.METRIC]
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: [route_without_metric],
        },
        base_con_profile=None,
    )
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == [
        route_with_default_metric
    ]


@parametrize_ip_ver_routes
def test_add_route_without_table_id(nm_ip, routes):
    route_with_default_table_id = copy.deepcopy(routes[0])
    route_with_default_table_id[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE
    route_without_table_id = copy.deepcopy(routes[0])
    del route_without_table_id[Route.TABLE_ID]
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: [route_without_table_id],
        },
        base_con_profile=None,
    )
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == [
        route_with_default_table_id
    ]


@parametrize_ip_ver_routes_gw
def test_change_gateway(nm_ip, routes, gateways):
    desired_routes = routes + gateways[:1]
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: desired_routes,
        },
        base_con_profile=None,
    )
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == routes
    assert _get_gateway(setting_ip) == gateways[0]


@pytest.mark.xfail(
    raises=NmstateNotImplementedError,
    strict=True,
    reason="Network Manager Bug: " "https://bugzilla.redhat.com/1707396",
)
@parametrize_ip_ver_routes_gw
def test_add_two_gateway(nm_ip, routes, gateways):
    nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: routes + gateways,
        },
        base_con_profile=None,
    )


@pytest.mark.xfail(
    raises=NmstateNotImplementedError,
    strict=True,
    reason="Network Manager Bug: " "https://bugzilla.redhat.com/1707396",
)
@parametrize_ip_ver_routes_gw
def test_add_duplicate_gateways(nm_ip, routes, gateways):
    nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: routes + [gateways[0], gateways[0]],
        },
        base_con_profile=None,
    )


@parametrize_ip_ver_routes_gw
def test_change_gateway_without_metric(nm_ip, routes, gateways):
    del gateways[0][Route.METRIC]
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: routes + [gateways[0]],
        },
        base_con_profile=None,
    )
    gateways[0][Route.METRIC] = Route.USE_DEFAULT_METRIC
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == routes
    assert _get_gateway(setting_ip) == gateways[0]


@parametrize_ip_ver_routes_gw
def test_change_gateway_without_table_id(nm_ip, routes, gateways):
    del gateways[0][Route.TABLE_ID]
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: routes + [gateways[0]],
        },
        base_con_profile=None,
    )
    gateways[0][Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE

    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == routes
    assert _get_gateway(setting_ip) == gateways[0]


@parametrize_ip_ver_routes_gw
def test_clear_gateway(nm_ip, routes, gateways, client_mock):
    setting_ip = nm_ip.create_setting(
        {
            InterfaceIP.ENABLED: True,
            BaseIface.ROUTES_METADATA: routes + gateways[:1],
        },
        base_con_profile=None,
    )
    con_profile = nm_connection.ConnectionProfile(client_mock)
    con_profile.create([setting_ip])
    setting_ip = nm_ip.create_setting(
        {InterfaceIP.ENABLED: True, BaseIface.ROUTES_METADATA: routes},
        base_con_profile=con_profile.profile,
    )
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == routes
    assert not setting_ip.get_gateway()
    assert setting_ip.get_route_table() == Route.USE_DEFAULT_ROUTE_TABLE
    assert setting_ip.props.route_metric == Route.USE_DEFAULT_METRIC


def _nm_route_to_dict(nm_route):
    dst = "{ip}/{prefix}".format(
        ip=nm_route.get_dest(), prefix=nm_route.get_prefix()
    )
    next_hop = nm_route.get_next_hop() or ""
    metric = int(nm_route.get_metric())
    table_id_variant = nm_route.get_attribute("table")

    return {
        Route.TABLE_ID: int(table_id_variant.get_uint32()),
        Route.DESTINATION: dst,
        Route.NEXT_HOP_ADDRESS: next_hop,
        Route.METRIC: metric,
    }


def _get_gateway(setting_ip):
    gateway = setting_ip.props.gateway
    if iplib.is_ipv6_address(gateway):
        destination = IPV6_DEFAULT_GATEWAY_DESTINATION
    else:
        destination = IPV4_DEFAULT_GATEWAY_DESTINATION
    return {
        Route.TABLE_ID: setting_ip.get_route_table(),
        Route.DESTINATION: destination,
        Route.NEXT_HOP_ADDRESS: gateway,
        Route.METRIC: setting_ip.get_route_metric(),
    }
