#
# Copyright (c) 2019 Red Hat, Inc.
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

from operator import itemgetter
import socket

from libnmstate import iplib
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .common import GLib
from .common import NM

IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"

# NM require route rule priority been set explicitly, use 30,000 when
# desire state instruct to use USE_DEFAULT_PRIORITY
ROUTE_RULE_DEFAULT_PRIORIRY = 30000


def get_running_config(applied_configs):
    """
    Query routes saved in running profile
    """
    routes = []
    for iface_name, applied_config in applied_configs.items():
        for ip_profile in (
            applied_config.get_setting_ip6_config(),
            applied_config.get_setting_ip4_config(),
        ):
            if not ip_profile:
                continue
            nm_routes = ip_profile.props.routes
            gateway = ip_profile.props.gateway
            if not nm_routes and not gateway:
                continue
            default_table_id = ip_profile.props.route_table
            if gateway:
                routes.append(
                    _get_default_route_config(
                        gateway,
                        ip_profile.props.route_metric,
                        default_table_id,
                        iface_name,
                    )
                )
            # NM supports multiple route table in single profile:
            # https://bugzilla.redhat.com/show_bug.cgi?id=1436531 The
            # `ipv4.route-table` and `ipv6.route-table` will be the default
            # table id for static routes and auto routes. But each static route
            # can still specify route table id.
            for nm_route in nm_routes:
                table_id = _get_per_route_table_id(nm_route, default_table_id)
                route_entry = _nm_route_to_route(
                    nm_route, table_id, iface_name
                )
                if route_entry:
                    routes.append(route_entry)
    routes.sort(
        key=itemgetter(
            Route.TABLE_ID, Route.NEXT_HOP_INTERFACE, Route.DESTINATION
        )
    )
    return routes


def _get_per_route_table_id(nm_route, default_table_id):
    table = nm_route.get_attribute(NM.IP_ROUTE_ATTRIBUTE_TABLE)
    return int(table.get_uint32()) if table else default_table_id


def _nm_route_to_route(nm_route, table_id, iface_name):
    dst = "{ip}/{prefix}".format(
        ip=nm_route.get_dest(), prefix=nm_route.get_prefix()
    )
    next_hop = nm_route.get_next_hop() or ""
    metric = int(nm_route.get_metric())

    return {
        Route.TABLE_ID: table_id,
        Route.DESTINATION: dst,
        Route.NEXT_HOP_INTERFACE: iface_name,
        Route.NEXT_HOP_ADDRESS: next_hop,
        Route.METRIC: metric,
    }


def _get_default_route_config(gateway, metric, default_table_id, iface_name):
    if iplib.is_ipv6_address(gateway):
        destination = IPV6_DEFAULT_GATEWAY_DESTINATION
    else:
        destination = IPV4_DEFAULT_GATEWAY_DESTINATION
    return {
        Route.TABLE_ID: default_table_id,
        Route.DESTINATION: destination,
        Route.NEXT_HOP_INTERFACE: iface_name,
        Route.NEXT_HOP_ADDRESS: gateway,
        Route.METRIC: metric,
    }


def add_routes(setting_ip, routes):
    for route in routes:
        _add_specfic_route(setting_ip, route)


def _add_specfic_route(setting_ip, route):
    destination, prefix_len = route[Route.DESTINATION].split("/")
    prefix_len = int(prefix_len)
    if iplib.is_ipv6_address(destination):
        family = socket.AF_INET6
    else:
        family = socket.AF_INET
    metric = route.get(Route.METRIC, Route.USE_DEFAULT_METRIC)
    next_hop = route[Route.NEXT_HOP_ADDRESS]
    ip_route = NM.IPRoute.new(
        family, destination, prefix_len, next_hop, metric
    )
    table_id = route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE)
    ip_route.set_attribute(
        NM.IP_ROUTE_ATTRIBUTE_TABLE, GLib.Variant.new_uint32(table_id)
    )
    # Duplicate route entry will be ignored by libnm.
    setting_ip.add_route(ip_route)


def get_static_gateway_iface(family, iface_routes):
    """
    Return one interface with gateway for given IP family.
    Return None if not found.
    """
    destination = (
        IPV6_DEFAULT_GATEWAY_DESTINATION
        if family == Interface.IPV6
        else IPV4_DEFAULT_GATEWAY_DESTINATION
    )
    for iface_name, routes in iface_routes.items():
        for route in routes:
            if route[Route.DESTINATION] == destination:
                return iface_name
    return None


def add_route_rules(setting_ip, family, rules):
    for rule in rules:
        setting_ip.add_routing_rule(_rule_info_to_nm_rule(rule, family))


def _rule_info_to_nm_rule(rule, family):
    nm_rule = NM.IPRoutingRule.new(family)
    ip_from = rule.get(RouteRule.IP_FROM)
    ip_to = rule.get(RouteRule.IP_TO)
    if not ip_from and not ip_to:
        raise NmstateValueError(
            f"Neither {RouteRule.IP_FROM} or {RouteRule.IP_TO} is defined"
        )

    if ip_from:
        nm_rule.set_from(*iplib.ip_address_full_to_tuple(ip_from))
    if ip_to:
        nm_rule.set_to(*iplib.ip_address_full_to_tuple(ip_to))

    priority = rule.get(RouteRule.PRIORITY)
    if priority and priority != RouteRule.USE_DEFAULT_PRIORITY:
        nm_rule.set_priority(priority)
    else:
        nm_rule.set_priority(ROUTE_RULE_DEFAULT_PRIORIRY)
    table = rule.get(RouteRule.ROUTE_TABLE)
    if table and table != RouteRule.USE_DEFAULT_ROUTE_TABLE:
        nm_rule.set_table(table)
    else:
        nm_rule.set_table(iplib.KERNEL_MAIN_ROUTE_TABLE_ID)
    return nm_rule
