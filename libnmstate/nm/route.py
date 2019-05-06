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

from operator import itemgetter
import socket

from libnmstate import iplib
from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.nm import nmclient
from libnmstate.nm.nmclient import GLib
from libnmstate.schema import Route

NM_ROUTE_TABLE_USE_DEFAULT_CFG = 0
NM_ROUTE_TABLE_ATTRIBUTE = 'table'
NM_ROUTE_DEFAULT_METRIC = -1
IPV4_DEFAULT_GATEWAY_DESTINATION = '0.0.0.0/0'
IPV6_DEFAULT_GATEWAY_DESTINATION = '::/0'


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
        iface_name = _get_iface_name(active_connection)
        if not iface_name:
            raise NmstateInternalError(
                'Got connection {} has not interface name'.format(
                    active_connection.get_id()))
        for nm_route in ip_cfg.props.routes:
            table_id = _get_per_route_table_id(
                nm_route,
                iplib.KERNEL_MAIN_ROUTE_TABLE_ID)
            route_entry = _nm_route_to_route(
                nm_route,
                table_id,
                iface_name)
            if route_entry:
                routes.append(route_entry)
    routes.sort(key=itemgetter(Route.TABLE_ID,
                               Route.NEXT_HOP_INTERFACE,
                               Route.DESTINATION))
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
        iface_name = _get_iface_name(active_connection)
        if not iface_name:
            raise NmstateInternalError(
                'Got connection {} has not interface name'.format(
                    active_connection.get_id()))
        default_table_id = ip_profile.props.route_table
        if gateway:
            routes.append(
                _get_default_route_config(
                    gateway,
                    ip_profile.props.route_metric,
                    default_table_id,
                    iface_name))
        # NM supports multiple route table in single profile:
        #   https://bugzilla.redhat.com/show_bug.cgi?id=1436531
        # The `ipv4.route-table` and `ipv6.route-table` will be the default
        # table id for static routes and auto routes. But each static route can
        # still specify route table id.
        for nm_route in nm_routes:
            table_id = _get_per_route_table_id(nm_route, default_table_id)
            route_entry = _nm_route_to_route(
                nm_route,
                table_id,
                iface_name)
            if route_entry:
                routes.append(route_entry)
    routes.sort(key=itemgetter(Route.TABLE_ID,
                               Route.NEXT_HOP_INTERFACE,
                               Route.DESTINATION))
    return routes


def _get_per_route_table_id(nm_route, default_table_id):
    table = nm_route.get_attribute(NM_ROUTE_TABLE_ATTRIBUTE)
    return int(table.get_uint32()) if table else default_table_id


def _get_iface_name(active_connection):
    """
    Return interface name for active_connection, return None if error.
    """
    devs = active_connection.get_devices()
    return devs[0].get_iface() if devs else None


def _nm_route_to_route(nm_route, table_id, iface_name):
    dst = '{ip}/{prefix_len}'.format(
        ip=nm_route.get_dest(), prefix_len=nm_route.get_prefix())
    next_hop = nm_route.get_next_hop() or ''
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
    default_gateway_defined = False
    for route in routes:
        if route[Route.DESTINATION] in (IPV4_DEFAULT_GATEWAY_DESTINATION,
                                        IPV6_DEFAULT_GATEWAY_DESTINATION):
            if default_gateway_defined:
                raise NmstateNotImplementedError(
                    'Only a single default gateway is supported.')
            default_gateway_defined = True
            _add_route_gateway(setting_ip, route)
        else:
            _add_specfic_route(setting_ip, route)


def _add_route_gateway(setting_ip, route):
    setting_ip.props.gateway = route[Route.NEXT_HOP_ADDRESS]
    if route[Route.TABLE_ID] != NM_ROUTE_TABLE_USE_DEFAULT_CFG:
        setting_ip.props.route_table = route[Route.TABLE_ID]
    if route[Route.METRIC] != NM_ROUTE_DEFAULT_METRIC:
        setting_ip.props.route_metric = route[Route.METRIC]


def _add_specfic_route(setting_ip, route):
    destination, prefix_len = route[Route.DESTINATION].split('/')
    prefix_len = int(prefix_len)
    family = socket.AF_INET6 if iplib.is_ipv6_address(destination) \
        else socket.AF_INET
    metric = route.get(Route.METRIC, NM_ROUTE_DEFAULT_METRIC)
    next_hop = route[Route.NEXT_HOP_ADDRESS]
    ip_route = nmclient.NM.IPRoute.new(family, destination, prefix_len,
                                       next_hop, metric)
    if route[Route.TABLE_ID] != NM_ROUTE_TABLE_USE_DEFAULT_CFG:
        ip_route.set_attribute(NM_ROUTE_TABLE_ATTRIBUTE,
                               GLib.Variant.new_uint32(route[Route.TABLE_ID]))
    setting_ip.add_route(ip_route)
