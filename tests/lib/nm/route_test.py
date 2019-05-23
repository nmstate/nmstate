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

import pytest

from libnmstate import metadata
from libnmstate.nm import ipv4 as nm_ipv4
from libnmstate.nm import ipv6 as nm_ipv6
from libnmstate.nm import connection as nm_connection
from libnmstate.schema import Route

IPV4_ROUTE1 = {
    Route.DESTINATION: '198.51.100.0/24',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '192.0.2.1',
    Route.TABLE_ID: 50
}

IPV4_ROUTE2 = {
    Route.DESTINATION: '203.0.113.0/24',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '192.0.2.2',
    Route.TABLE_ID: 51
}

IPV6_ROUTE1 = {
    Route.DESTINATION: '2001:db8:a::/64',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '2001:db8:1::a',
    Route.TABLE_ID: 50
}

IPV6_ROUTE2 = {
    Route.DESTINATION: '2001:db8:b::/64',
    Route.METRIC: 103,
    Route.NEXT_HOP_ADDRESS: '2001:db8:1::b',
    Route.TABLE_ID: 51
}

parametrize_ip_ver_routes = pytest.mark.parametrize(
    'nm_ip, routes',
    [(nm_ipv4, [IPV4_ROUTE1, IPV4_ROUTE2]),
     (nm_ipv6, [IPV6_ROUTE1, IPV6_ROUTE2])],
    ids=['ipv4', 'ipv6'])


@parametrize_ip_ver_routes
def test_add_multiple_route(nm_ip, routes):
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        metadata.ROUTES: routes
    }, base_con_profile=None)
    assert [_nm_route_to_dict(r) for r in setting_ip.props.routes] == routes


@parametrize_ip_ver_routes
def test_add_duplicate_routes(nm_ip, routes):
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        metadata.ROUTES: [routes[0], routes[0]]
    }, base_con_profile=None)
    assert ([_nm_route_to_dict(r) for r in setting_ip.props.routes] ==
            [routes[0]])


@parametrize_ip_ver_routes
def test_clear_route(nm_ip, routes):
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        metadata.ROUTES: routes
    }, base_con_profile=None)
    con_profile = nm_connection.ConnectionProfile()
    con_profile.create([setting_ip])
    new_setting_ip = nm_ip.create_setting({
        'enabled': True,
        metadata.ROUTES: []
    }, base_con_profile=con_profile.profile)
    assert not [_nm_route_to_dict(r) for r in new_setting_ip.props.routes]


@parametrize_ip_ver_routes
def test_add_route_without_metric(nm_ip, routes):
    route_with_default_metric = copy.deepcopy(routes[0])
    route_with_default_metric[Route.METRIC] = Route.USE_DEFAULT_METRIC
    route_without_metric = copy.deepcopy(routes[0])
    del route_without_metric[Route.METRIC]
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        metadata.ROUTES: [route_without_metric]
    }, base_con_profile=None)
    assert ([_nm_route_to_dict(r) for r in setting_ip.props.routes] ==
            [route_with_default_metric])


@parametrize_ip_ver_routes
def test_add_route_without_table_id(nm_ip, routes):
    route_with_default_table_id = copy.deepcopy(routes[0])
    route_with_default_table_id[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE
    route_without_table_id = copy.deepcopy(routes[0])
    del route_without_table_id[Route.TABLE_ID]
    setting_ip = nm_ip.create_setting({
        'enabled': True,
        metadata.ROUTES: [route_without_table_id]
    }, base_con_profile=None)
    assert ([_nm_route_to_dict(r) for r in setting_ip.props.routes] ==
            [route_with_default_table_id])


def _nm_route_to_dict(nm_route):
    dst = '{ip}/{prefix}'.format(
        ip=nm_route.get_dest(), prefix=nm_route.get_prefix())
    next_hop = nm_route.get_next_hop() or ''
    metric = int(nm_route.get_metric())
    table_id_variant = nm_route.get_attribute('table')

    return {
        Route.TABLE_ID: int(table_id_variant.get_uint32()),
        Route.DESTINATION: dst,
        Route.NEXT_HOP_ADDRESS: next_hop,
        Route.METRIC: metric,
    }
