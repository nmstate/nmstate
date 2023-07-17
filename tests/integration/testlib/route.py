# SPDX-License-Identifier: LGPL-2.1-or-later

import copy

from libnmstate.schema import Route


def _assert_in_current_route(route, current_routes):
    route_in_current_routes = False
    for current_route in current_routes:
        current_route.pop(Route.METRIC, None)
        table_id = route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE)
        if table_id == Route.USE_DEFAULT_ROUTE_TABLE:
            current_route = copy.deepcopy(current_route)
            current_route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE

        if route == current_route:
            route_in_current_routes = True
            break
    assert route_in_current_routes


def assert_routes(routes, state, nic="eth1"):
    routes = copy.deepcopy(routes)
    for route in routes:
        # Ignore metric difference like nmstate production code
        route.pop(Route.METRIC, None)
        if Route.TABLE_ID not in route:
            route[Route.TABLE_ID] = Route.USE_DEFAULT_ROUTE_TABLE
    routes.sort(key=_route_sort_key)
    config_routes = []
    for config_route in state[Route.KEY][Route.CONFIG]:
        if config_route[Route.NEXT_HOP_INTERFACE] == nic:
            config_routes.append(config_route)

    # The kernel routes contains more route entries than desired config
    # The kernel routes also has different metric and table id for
    # USE_DEFAULT_ROUTE_TABLE and USE_DEFAULT_METRIC
    config_routes.sort(key=_route_sort_key)
    for route in routes:
        _assert_in_current_route(route, config_routes)
    running_routes = state[Route.KEY][Route.RUNNING]
    for route in routes:
        _assert_in_current_route(route, running_routes)


def _route_sort_key(route):
    return (
        route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
        route.get(Route.NEXT_HOP_INTERFACE, ""),
        route.get(Route.DESTINATION, ""),
    )
