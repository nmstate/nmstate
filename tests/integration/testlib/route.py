# SPDX-License-Identifier: LGPL-2.1-or-later

import copy

from libnmstate.schema import Route


def assert_routes(routes, state, nic="eth1"):
    routes = _clone_prepare_routes(routes)
    config_routes = _clone_prepare_routes(state[Route.KEY][Route.CONFIG], nic)
    running_routes = _clone_prepare_routes(
        state[Route.KEY][Route.RUNNING], nic
    )

    # The kernel contains more route entries than desired config
    for route in routes:
        assert any(_compare_route(route, c_r) for c_r in config_routes)
        assert any(_compare_route(route, r_r) for r_r in running_routes)


def assert_routes_missing(routes, state, nic="eth1"):
    routes = _clone_prepare_routes(routes)
    config_routes = _clone_prepare_routes(state[Route.KEY][Route.CONFIG], nic)
    running_routes = _clone_prepare_routes(
        state[Route.KEY][Route.RUNNING], nic
    )

    # The kernel contains more route entries than desired config
    for route in routes:
        assert all(not _compare_route(route, c_r) for c_r in config_routes)
        assert all(not _compare_route(route, r_r) for r_r in running_routes)


def _clone_prepare_routes(routes, nic=None):
    routes_out = []
    for route in routes:
        if nic is None or route.get(Route.NEXT_HOP_INTERFACE, None) == nic:
            # The kernel routes has different metric and table id for
            # USE_DEFAULT_ROUTE_TABLE and USE_DEFAULT_METRIC
            route = copy.deepcopy(route)
            route.pop(Route.METRIC, None)
            if Route.TABLE_ID not in route:
                route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE
            routes_out.append(route)

    routes_out.sort(key=_route_sort_key)
    return routes_out


def _compare_route(route, current_route):
    # kernel uses different value for the default table id
    table_id = route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE)
    if table_id == Route.USE_DEFAULT_ROUTE_TABLE:
        current_route = copy.deepcopy(current_route)
        current_route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE

    return route == current_route


def _route_sort_key(route):
    return (
        route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
        route.get(Route.NEXT_HOP_INTERFACE, ""),
        route.get(Route.DESTINATION, ""),
    )
