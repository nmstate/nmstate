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
from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError
from libnmstate.nm import nmclient
from libnmstate.nm import active_connection as nm_ac
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

NM_ROUTE_TABLE_ATTRIBUTE = "table"
IPV4_DEFAULT_GATEWAY_DESTINATION = "0.0.0.0/0"
IPV6_DEFAULT_GATEWAY_DESTINATION = "::/0"
ROUTE_METADATA = "_routes"
ROUTE_RULES_METADATA = "_route_rules"

# NM require route rule priority been set explicitly, use 30,000 when
# desire state instruct to use USE_DEFAULT_PRIORITY
ROUTE_RULE_DEFAULT_PRIORIRY = 30000


def get_running(acs_and_ip_cfgs):
    """
    Query running routes
    The acs_and_ip_cfgs should be generate to generate a tuple:
        NM.NM.ActiveConnection, NM.IPConfig
    """
    routes = []
    for (active_connection, ip_cfg) in acs_and_ip_cfgs:
        if not ip_cfg.props.routes:
            continue
        iface_name = nm_ac.ActiveConnection(active_connection).devname
        if not iface_name:
            raise NmstateInternalError(
                "Got connection {} has not interface name".format(
                    active_connection.get_id()
                )
            )
        for nm_route in ip_cfg.props.routes:
            table_id = _get_per_route_table_id(
                nm_route, iplib.KERNEL_MAIN_ROUTE_TABLE_ID
            )
            route_entry = _nm_route_to_route(nm_route, table_id, iface_name)
            if route_entry:
                routes.append(route_entry)
    routes.sort(
        key=itemgetter(
            Route.TABLE_ID, Route.NEXT_HOP_INTERFACE, Route.DESTINATION
        )
    )
    return routes


def get_config(acs_and_ip_profiles):
    """
    Query running routes
    The acs_and_ip_profiles should be generate to generate a tuple:
        NM.NM.ActiveConnection, NM.SettingIPConfig
    """
    routes = []
    for (active_connection, ip_profile) in acs_and_ip_profiles:
        nm_routes = ip_profile.props.routes
        gateway = ip_profile.props.gateway
        if not nm_routes and not gateway:
            continue
        iface_name = nm_ac.ActiveConnection(active_connection).devname
        if not iface_name:
            raise NmstateInternalError(
                "Got connection {} has not interface name".format(
                    active_connection.get_id()
                )
            )
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
        #   https://bugzilla.redhat.com/show_bug.cgi?id=1436531
        # The `ipv4.route-table` and `ipv6.route-table` will be the default
        # table id for static routes and auto routes. But each static route can
        # still specify route table id.
        for nm_route in nm_routes:
            table_id = _get_per_route_table_id(nm_route, default_table_id)
            route_entry = _nm_route_to_route(nm_route, table_id, iface_name)
            if route_entry:
                routes.append(route_entry)
    routes.sort(
        key=itemgetter(
            Route.TABLE_ID, Route.NEXT_HOP_INTERFACE, Route.DESTINATION
        )
    )
    return routes


def _get_per_route_table_id(nm_route, default_table_id):
    table = nm_route.get_attribute(NM_ROUTE_TABLE_ATTRIBUTE)
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
        if route[Route.DESTINATION] in (
            IPV4_DEFAULT_GATEWAY_DESTINATION,
            IPV6_DEFAULT_GATEWAY_DESTINATION,
        ):
            if setting_ip.get_gateway():
                raise NmstateNotImplementedError(
                    "Only a single default gateway is supported due to a "
                    "limitation of NetworkManager: "
                    "https://bugzilla.redhat.com/1707396"
                )
            _add_route_gateway(setting_ip, route)
        else:
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
    ip_route = nmclient.NM.IPRoute.new(
        family, destination, prefix_len, next_hop, metric
    )
    table_id = route.get(Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE)
    ip_route.set_attribute(
        NM_ROUTE_TABLE_ATTRIBUTE, nmclient.GLib.Variant.new_uint32(table_id)
    )
    # Duplicate route entry will be ignored by libnm.
    setting_ip.add_route(ip_route)


def _add_route_gateway(setting_ip, route):
    setting_ip.props.gateway = route[Route.NEXT_HOP_ADDRESS]
    setting_ip.props.route_table = route.get(
        Route.TABLE_ID, Route.USE_DEFAULT_ROUTE_TABLE
    )
    setting_ip.props.route_metric = route.get(
        Route.METRIC, Route.USE_DEFAULT_METRIC
    )


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


def get_routing_rule_config(acs_and_ip_profiles):
    rules = []
    for (_, ip_profile) in acs_and_ip_profiles:
        for i in range(ip_profile.get_num_routing_rules()):
            nm_rule = ip_profile.get_routing_rule(i)
            rules.append(_nm_rule_to_info(nm_rule))

    return rules


def _nm_rule_to_info(nm_rule):
    info = {
        RouteRule.IP_FROM: _nm_rule_get_from(nm_rule),
        RouteRule.IP_TO: _nm_rule_get_to(nm_rule),
        RouteRule.PRIORITY: nm_rule.get_priority(),
        RouteRule.ROUTE_TABLE: nm_rule.get_table(),
    }
    cleanup_keys = [key for key, val in info.items() if val is None]
    for key in cleanup_keys:
        del info[key]

    return info


def _nm_rule_get_from(nm_rule):
    if nm_rule.get_from():
        return iplib.to_ip_address_full(
            nm_rule.get_from(), nm_rule.get_from_len()
        )
    return None


def _nm_rule_get_to(nm_rule):
    if nm_rule.get_to():
        return iplib.to_ip_address_full(nm_rule.get_to(), nm_rule.get_to_len())
    return None


def add_route_rules(setting_ip, family, rules):
    for rule in rules:
        setting_ip.add_routing_rule(_rule_info_to_nm_rule(rule, family))


def _rule_info_to_nm_rule(rule, family):
    nm_rule = nmclient.NM.IPRoutingRule.new(family)
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
