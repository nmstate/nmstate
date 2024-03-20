# SPDX-License-Identifier: LGPL-2.1-or-later

import copy

from libnmstate.schema import Route


KERNEL_DEFAULT_TABLE_ID = 254


def assert_routes(routes, state, nic="eth1"):
    routes = _clone_prepare_routes(routes)
    config_routes = _clone_prepare_routes(state[Route.KEY][Route.CONFIG], nic)
    running_routes = _clone_prepare_routes(
        state[Route.KEY][Route.RUNNING], nic
    )

    # The kernel contains more route entries than desired config
    for route in routes:
        assert any(route == cur_rt for cur_rt in config_routes)
        assert any(route == run_rt for run_rt in running_routes)


def assert_routes_missing(routes, state, nic="eth1"):
    routes = _clone_prepare_routes(routes)
    config_routes = _clone_prepare_routes(state[Route.KEY][Route.CONFIG], nic)
    running_routes = _clone_prepare_routes(
        state[Route.KEY][Route.RUNNING], nic
    )

    # The kernel contains more route entries than desired config
    for route in routes:
        assert all(route != cur_rt for cur_rt in config_routes)
        assert all(route != run_rt for run_rt in running_routes)


def _clone_prepare_routes(routes, nic=None):
    routes_out = []
    for route in routes:
        if nic is None or route.get(Route.NEXT_HOP_INTERFACE, None) == nic:
            route = copy.deepcopy(route)
            # Ignore metric difference like nmstate production code
            route.pop(Route.METRIC, None)
            # Compare using kernel's value for the default table_id as it's not
            # the same than USE_DEFAULT_ROUTE_TABLE
            table_id = route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE)
            if table_id == Route.USE_DEFAULT_ROUTE_TABLE:
                route[Route.TABLE_ID] = KERNEL_DEFAULT_TABLE_ID

            routes_out.append(route)

    routes_out.sort(key=_route_sort_key)
    return routes_out


def _route_sort_key(route):
    return (
        route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE),
        route.get(Route.NEXT_HOP_INTERFACE, ""),
        route.get(Route.DESTINATION, ""),
    )
