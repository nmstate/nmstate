#
# Copyright 2018 Red Hat, Inc.
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
from __future__ import absolute_import

import jsonschema as js
import logging
import six

from . import nm
from . import schema
from .schema import Constants
from libnmstate.nm import route as nm_route


class LinkAggregationSlavesMissingError(Exception):
    pass


class LinkAggregationSlavesReuseError(Exception):
    pass


class CapabilityNotSupportedError(Exception):
    pass


class MultipleRouteTablesNotSupportedError(Exception):
    pass


class InvalidRouteTableValueError(Exception):
    pass


class StaticRouteOnAutoIPNotSupportedError(Exception):
    pass


class AutoRouteOnStaticIPNotSupportedError(Exception):
    pass


class CannotSetOfflineRouteError(Exception):
    pass


def verify(data, validation_schema=schema.ifaces_schema):
    js.validate(data, validation_schema)


def verify_capabilities(state, capabilities):
    verify_interface_capabilities(state[Constants.INTERFACES], capabilities)


def verify_interface_capabilities(ifaces_state, capabilities):
    ifaces_types = [iface_state['type'] for iface_state in ifaces_state]
    has_ovs_capability = nm.ovs.CAPABILITY in capabilities
    for iface_type in ifaces_types:
        is_ovs_type = iface_type in (
            nm.ovs.BRIDGE_TYPE,
            nm.ovs.PORT_TYPE,
            nm.ovs.INTERNAL_INTERFACE_TYPE
        )
        if is_ovs_type and not has_ovs_capability:
            raise CapabilityNotSupportedError(iface_type)


def verify_interfaces_state(ifaces_state, ifaces_desired_state):
    verify_link_aggregation_state(ifaces_state, ifaces_desired_state)


def verify_link_aggregation_state(ifaces_state, ifaces_desired_state):
    available_ifaces = {
        iface_state['name'] for iface_state in ifaces_state
        if iface_state.get('state') != 'absent'
    }
    available_ifaces |= {
        ifname for ifname, ifstate in six.viewitems(ifaces_desired_state)
        if ifstate.get('state') != 'absent'
    }
    specified_slaves = set()
    for iface_state in ifaces_state:
        if iface_state.get('state') != 'absent':
            link_aggregation = iface_state.get('link-aggregation')
            if link_aggregation:
                slaves = set(link_aggregation.get('slaves', []))
                if not (slaves <= available_ifaces):
                    raise LinkAggregationSlavesMissingError(iface_state)
                if slaves & specified_slaves:
                    raise LinkAggregationSlavesReuseError(iface_state)
                specified_slaves |= slaves


def verify_dhcp(state):
    for iface_state in state[Constants.INTERFACES]:
        for family in ('ipv4', 'ipv6'):
            ip = iface_state.get(family, {})
            if ip.get('enabled') and ip.get('address') and \
               (ip.get('dhcp') or ip.get('autoconf')):
                logging.warning('%s addresses are ignored when '
                                'dynamic IP is enabled', family)


def verify_ifaces_routing_state(ifaces_routing_state, ifaces_state):
    for iface_name, iface_routing_state in six.viewitems(ifaces_routing_state):
        _verify_route_on_offline_iface(ifaces_state[iface_name],
                                       iface_routing_state)
        _verify_mixing_auto_static_route(ifaces_state[iface_name],
                                         iface_routing_state)
        _verify_route_table_value(iface_routing_state)
        _verify_mixing_auto_static_route(ifaces_state[iface_name],
                                         iface_routing_state)


def _verify_route_on_offline_iface(iface_state, iface_routing_state):
    iface_is_disabled = iface_state['state'] != 'up'
    for family in ('ipv4', 'ipv6'):
        if iface_routing_state[family] and iface_is_disabled:
            raise CannotSetOfflineRouteError(
                'Cannot set {} route when interface {} is down'.format(
                    family, iface_state['name']))
        if iface_routing_state[family] and \
           not iface_state[family]['enabled']:
            raise CannotSetOfflineRouteError(
                'Cannot set {} route when {} is disabled on '
                'interface {}'.format(family, family, iface_state['name']))


def _verify_mixing_auto_static_route(iface_state, iface_routing_state):
    for family in ('ipv4', 'ipv6'):
        iface_ip_conf = iface_state.get(family, {})
        flag_auto_ip = iface_ip_conf.get('dhcp') or \
            iface_ip_conf.get('autoconf')
        for route in iface_routing_state[family]:
            if flag_auto_ip and route['route-type'] != 'auto':
                raise StaticRouteOnAutoIPNotSupportedError(
                    'Cannot set static route on auto {} interface {}'.format(
                        family, iface_state['name']))
            if not flag_auto_ip and route['route-type'] == 'auto':
                raise AutoRouteOnStaticIPNotSupportedError(
                    'Cannot set auto route on static {} interface {}'.format(
                        family, iface_state['name']))


def _verify_route_table_value(iface_routing_state):
    for family in ('ipv4', 'ipv6'):
        route_tables = set(route['route-table']
                           for route in iface_routing_state[family])
        if len(route_tables) == 0:
            # Will use main route table If empty
            continue
        if len(route_tables) > 1:
            raise MultipleRouteTablesNotSupportedError(
                'Multiple route tables on one interface is not supported')
        route_table = route_tables.pop()
        if route_table == nm_route.MAIN_ROUTE_TABLE:
            continue
        try:
            int(route_table)
        except ValueError:
            raise InvalidRouteTableValueError(
                'Specified route table should be integer or \'main\'')
