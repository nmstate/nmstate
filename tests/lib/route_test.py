# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route

from libnmstate.ifaces import BaseIface
from libnmstate.route import RouteEntry
from libnmstate.route import RouteState

from .testlib.ifacelib import gen_two_static_ip_ifaces
from .testlib.routelib import IPV4_ROUTE_IFACE_NAME
from .testlib.routelib import IPV4_ROUTE_DESITNATION
from .testlib.routelib import IPV6_ROUTE_IFACE_NAME
from .testlib.routelib import gen_ipv4_route
from .testlib.routelib import gen_ipv6_route


parametrize_route_property = pytest.mark.parametrize(
    "route_property",
    [
        Route.TABLE_ID,
        Route.DESTINATION,
        Route.NEXT_HOP_INTERFACE,
        Route.NEXT_HOP_ADDRESS,
        Route.METRIC,
    ],
)


class TestRouteEntry:
    def test_hash_unique(self):
        route = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)
        assert hash(route) == hash(route)

    def test_obj_unique(self):
        route0 = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)
        route1 = _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )
        route0_clone = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        assert route0 == route0_clone
        assert route0 != route1

    def test_obj_unique_without_table_id(self):
        route_with_default_table_id = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            Route.USE_DEFAULT_ROUTE_TABLE,
            103,
        )

        route_without_table_id = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", None, 103
        )

        assert route_without_table_id == route_with_default_table_id

    def test_obj_unique_without_metric(self):
        route_with_default_metric = _create_route(
            "198.51.100.0/24",
            "192.0.2.1",
            "eth1",
            50,
            Route.USE_DEFAULT_METRIC,
        )

        route_without_metric = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, None
        )

        assert route_without_metric == route_with_default_metric

    def test_obj_unique_without_next_hop(self):
        route_with_default_next_hop = _create_route(
            "198.51.100.0/24", "", "eth1", 50, 103
        )

        route_without_next_hop = _create_route(
            "198.51.100.0/24", None, "eth1", 50, 103
        )

        assert route_without_next_hop == route_with_default_next_hop

    def test_normal_route_object_as_dict(self):
        route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        route_obj = RouteEntry(route)
        assert route_obj.to_dict() == route

    def test_absent_route_object_as_dict(self):
        route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        route[Route.STATE] = Route.STATE_ABSENT
        route_obj = RouteEntry(route)
        assert route_obj.absent
        assert route_obj.to_dict() == route

    @parametrize_route_property
    def test_absent_route_with_missing_props_as_dict(self, route_property):
        absent_route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        absent_route[Route.STATE] = Route.STATE_ABSENT
        del absent_route[route_property]
        route_obj = RouteEntry(absent_route)
        assert route_obj.to_dict() == absent_route

    def test_absent_route_with_exact_match(self):
        route0 = _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 50, 103)

        absent_r0 = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        absent_r0[Route.STATE] = Route.STATE_ABSENT
        absent_route0 = RouteEntry(absent_r0)

        route1 = _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )

        assert absent_route0.match(route0)
        assert absent_route0 == route0
        assert not absent_route0.match(route1)
        assert absent_route0 != route1

    @parametrize_route_property
    def test_absent_route_wildcard_match(self, route_property):
        original_route0 = _create_route(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        original_route1 = _create_route(
            "2001:db8:a::/64", "2001:db8:1::a", "eth2", 51, 104
        )

        absent_route0_state = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        absent_route0_state[Route.STATE] = Route.STATE_ABSENT
        del absent_route0_state[route_property]
        new_route0 = RouteEntry(absent_route0_state)

        assert new_route0.match(original_route0)
        assert not new_route0.match(original_route1)

    def test_absent_route_is_ignored_for_matching_and_equality(self):
        route = _create_route_dict(
            "198.51.100.0/24", "192.0.2.1", "eth1", 50, 103
        )
        route[Route.STATE] = Route.STATE_ABSENT
        obj1 = RouteEntry(route)
        obj2 = RouteEntry(route)
        assert obj1.match(obj2)
        assert obj1 == obj2

    def test_sort_routes(self):
        routes = [
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.3", "eth1", 10, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 101),
        ]
        expected_routes = [
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 101),
            _create_route("198.51.100.0/24", "192.0.2.3", "eth1", 10, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
        ]
        assert expected_routes == sorted(routes)

    @parametrize_route_property
    def test_sort_routes_with_absent_route(self, route_property):
        absent_route = _create_route(
            "198.51.100.0/24", "192.0.1.1", "eth0", 9, 103
        ).to_dict()
        absent_route[Route.STATE] = Route.STATE_ABSENT
        del absent_route[route_property]
        absent_route = RouteEntry(absent_route)
        routes = [
            absent_route,
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 103),
        ]
        expected_routes = [
            absent_route,
            _create_route("198.51.100.0/24", "192.0.2.1", "eth1", 10, 103),
            _create_route("198.51.100.0/24", "192.0.2.1", "eth0", 50, 103),
            _create_route("198.51.100.1/24", "192.0.2.1", "eth0", 50, 103),
        ]
        assert expected_routes == sorted(routes)


class TestRouteState:
    def _gen_ifaces(self):
        return gen_two_static_ip_ifaces(
            IPV4_ROUTE_IFACE_NAME, IPV6_ROUTE_IFACE_NAME
        )

    def _gen_route_state(self, des_routes, cur_routes):
        return RouteState(
            self._gen_ifaces(),
            {Route.CONFIG: [r.to_dict() for r in des_routes]},
            {Route.CONFIG: [r.to_dict() for r in cur_routes]},
        )

    def test_merge_empty_states(self):
        state = RouteState(self._gen_ifaces(), [], [])

        assert {} == state.config_iface_routes

    def test_merge_identical_states(self):
        ipv4_route = gen_ipv4_route()

        state = self._gen_route_state([ipv4_route], [ipv4_route])

        assert [IPV4_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV4_ROUTE_IFACE_NAME] == set(
            [ipv4_route]
        )

    def test_merge_unique_states(self):
        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = self._gen_route_state([ipv4_route], [ipv6_route])

        assert [IPV4_ROUTE_IFACE_NAME, IPV6_ROUTE_IFACE_NAME] == sorted(
            list(state.config_iface_routes.keys())
        )
        assert state.config_iface_routes[IPV4_ROUTE_IFACE_NAME] == set(
            [ipv4_route]
        )
        assert state.config_iface_routes[IPV6_ROUTE_IFACE_NAME] == set(
            [ipv6_route]
        )

    def test_merge_empty_with_non_empty_state(self):
        ipv4_route = gen_ipv4_route()

        state = self._gen_route_state([], [ipv4_route])
        assert [IPV4_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV4_ROUTE_IFACE_NAME] == set(
            [ipv4_route]
        )

    def test_remove_route_with_exact_match(self):
        ipv4_route = gen_ipv4_route()
        ipv4_route_absent_dict = gen_ipv4_route().to_dict()
        ipv4_route_absent_dict[Route.STATE] = Route.STATE_ABSENT
        ipv4_route_absent = RouteEntry(ipv4_route_absent_dict)

        state = self._gen_route_state([ipv4_route_absent], [ipv4_route])

        assert not list(state.config_iface_routes.keys())

    def test_remove_route_with_wildcard_match_with_next_hop_iface(self):
        ipv4_route = gen_ipv4_route()
        route_absent = RouteEntry(
            {
                Route.NEXT_HOP_INTERFACE: IPV4_ROUTE_IFACE_NAME,
                Route.STATE: Route.STATE_ABSENT,
            }
        )
        state = self._gen_route_state([route_absent], [ipv4_route])
        assert not list(state.config_iface_routes.keys())

    def test_remove_route_with_wildcard_match_without_next_hop_iface(self):
        ipv4_route = gen_ipv4_route()
        route_absent = RouteEntry(
            {
                Route.DESTINATION: IPV4_ROUTE_DESITNATION,
                Route.STATE: Route.STATE_ABSENT,
            }
        )
        state = self._gen_route_state([route_absent], [ipv4_route])
        assert not list(state.config_iface_routes.keys())

    def test_validate_route_to_abent_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[
            IPV4_ROUTE_IFACE_NAME
        ].state = InterfaceState.ABSENT

        ipv4_route = gen_ipv4_route()
        with pytest.raises(NmstateValueError):
            RouteState(ifaces, {Route.CONFIG: [ipv4_route.to_dict()]}, [])

    def test_validate_route_to_down_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[
            IPV4_ROUTE_IFACE_NAME
        ].state = InterfaceState.DOWN

        ipv4_route = gen_ipv4_route()
        with pytest.raises(NmstateValueError):
            RouteState(ifaces, {Route.CONFIG: [ipv4_route.to_dict()]}, [])

    def test_validate_route_to_ipv4_disabled(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME].raw[Interface.IPV4][
            InterfaceIPv4.ENABLED
        ] = False

        ipv4_route = gen_ipv4_route()
        with pytest.raises(NmstateValueError):
            RouteState(ifaces, {Route.CONFIG: [ipv4_route.to_dict()]}, [])

    def test_validate_route_to_ipv6_disabled(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME].raw[Interface.IPV6][
            InterfaceIPv6.ENABLED
        ] = False

        ipv6_route = gen_ipv6_route()
        with pytest.raises(NmstateValueError):
            RouteState(ifaces, {Route.CONFIG: [ipv6_route.to_dict()]}, [])

    def test_validate_route_without_next_hop_iface(self):
        ipv4_route_dict = gen_ipv4_route().to_dict()
        ipv4_route_dict.pop(Route.NEXT_HOP_INTERFACE)
        with pytest.raises(NmstateValueError):
            self._gen_route_state([RouteEntry(ipv4_route_dict)], [])

    def test_validate_route_without_destination(self):
        ipv4_route_dict = gen_ipv4_route().to_dict()
        ipv4_route_dict.pop(Route.DESTINATION)
        with pytest.raises(NmstateValueError):
            self._gen_route_state([RouteEntry(ipv4_route_dict)], [])

    def test_validate_route_next_hop_to_unknown_iface(self):
        ipv4_route_dict = gen_ipv4_route().to_dict()
        ipv4_route_dict[Route.NEXT_HOP_INTERFACE] = "not_exit_iface"
        with pytest.raises(NmstateValueError):
            self._gen_route_state([RouteEntry(ipv4_route_dict)], [])

    def test_validate_route_next_hop_to_dhcpv4_ifce(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME].raw[Interface.IPV4][
            InterfaceIPv4.DHCP
        ] = True

        ipv4_route = gen_ipv4_route()
        RouteState(ifaces, {Route.CONFIG: [ipv4_route.to_dict()]}, [])

    def test_validate_route_next_hop_to_dhcpv6_ifce(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME].raw[Interface.IPV6][
            InterfaceIPv6.DHCP
        ] = True

        ipv6_route = gen_ipv6_route()
        RouteState(ifaces, {Route.CONFIG: [ipv6_route.to_dict()]}, [])

    def test_validate_route_next_hop_to_ipv6_autoconf_ifce(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME].raw[Interface.IPV6][
            InterfaceIPv6.AUTOCONF
        ] = True

        ipv6_route = gen_ipv6_route()
        RouteState(ifaces, {Route.CONFIG: [ipv6_route.to_dict()]}, [])

    def test_discard_route_next_hop_absent_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[
            IPV4_ROUTE_IFACE_NAME
        ].state = InterfaceState.ABSENT

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV6_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV6_ROUTE_IFACE_NAME] == set(
            [ipv6_route]
        )

    def test_discard_route_next_hop_down_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[
            IPV4_ROUTE_IFACE_NAME
        ].state = InterfaceState.DOWN

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV6_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV6_ROUTE_IFACE_NAME] == set(
            [ipv6_route]
        )

    def test_discard_route_next_hop_ipv4_disabled_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME].raw[Interface.IPV4][
            InterfaceIPv4.ENABLED
        ] = False

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV6_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV6_ROUTE_IFACE_NAME] == set(
            [ipv6_route]
        )

    def test_discard_route_next_hop_ipv6_disabled_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME].raw[Interface.IPV6][
            InterfaceIPv6.ENABLED
        ] = False

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV4_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV4_ROUTE_IFACE_NAME] == set(
            [ipv4_route]
        )

    def test_discard_route_next_hop_dhcpv4_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME].raw[Interface.IPV4][
            InterfaceIPv4.DHCP
        ] = True

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV6_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV6_ROUTE_IFACE_NAME] == set(
            [ipv6_route]
        )

    def test_discard_route_next_hop_dhcpv6_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME].raw[Interface.IPV6][
            InterfaceIPv6.DHCP
        ] = True

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV4_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV4_ROUTE_IFACE_NAME] == set(
            [ipv4_route]
        )

    def test_discard_route_next_hop_ipv6_autoconf_iface(self):
        ifaces = self._gen_ifaces()
        ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME].raw[Interface.IPV6][
            InterfaceIPv6.AUTOCONF
        ] = True

        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        assert [IPV4_ROUTE_IFACE_NAME] == list(
            state.config_iface_routes.keys()
        )
        assert state.config_iface_routes[IPV4_ROUTE_IFACE_NAME] == set(
            [ipv4_route]
        )

    def test_gen_metadata(self):
        ifaces = self._gen_ifaces()
        ipv4_route = gen_ipv4_route()
        ipv6_route = gen_ipv6_route()
        route_state = RouteState(
            ifaces,
            [],
            {Route.CONFIG: [ipv4_route.to_dict(), ipv6_route.to_dict()]},
        )
        ifaces.gen_route_metadata(route_state)

        ipv4_route_iface = ifaces.all_kernel_ifaces[IPV4_ROUTE_IFACE_NAME]
        ipv6_route_iface = ifaces.all_kernel_ifaces[IPV6_ROUTE_IFACE_NAME]

        assert ipv4_route_iface.to_dict()[Interface.IPV4][
            BaseIface.ROUTES_METADATA
        ] == [ipv4_route.to_dict()]
        assert ipv6_route_iface.to_dict()[Interface.IPV6][
            BaseIface.ROUTES_METADATA
        ] == [ipv6_route.to_dict()]


def _create_route(dest, via_addr, via_iface, table, metric):
    return RouteEntry(
        _create_route_dict(dest, via_addr, via_iface, table, metric)
    )


def _create_route_dict(dest, via_addr, via_iface, table, metric):
    return {
        Route.DESTINATION: dest,
        Route.METRIC: metric,
        Route.NEXT_HOP_ADDRESS: via_addr,
        Route.NEXT_HOP_INTERFACE: via_iface,
        Route.TABLE_ID: table,
    }
