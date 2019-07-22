#
# Copyright (c) 2018-2019 Red Hat, Inc.
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
import logging
import six

import jsonschema as js

from . import nm
from . import schema
from .schema import Constants
from libnmstate.schema import DNS
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv6
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError
from libnmstate.iplib import is_ipv6_address


class NmstateRouteWithNoInterfaceError(NmstateValueError):
    pass


class NmstateRouteWithNoUpInterfaceError(NmstateValueError):
    pass


class NmstateRouteWithNoIPInterfaceError(NmstateValueError):
    pass


def validate(data, validation_schema=schema.ifaces_schema):
    data = copy.deepcopy(data)
    for ifstate in data.get(schema.Interface.KEY, ()):
        if not ifstate.get(schema.Interface.TYPE):
            ifstate[schema.Interface.TYPE] = schema.InterfaceType.UNKNOWN
    js.validate(data, validation_schema)


def validate_capabilities(state, capabilities):
    validate_interface_capabilities(state[Constants.INTERFACES], capabilities)


def validate_interface_capabilities(ifaces_state, capabilities):
    ifaces_types = [iface_state.get('type') for iface_state in ifaces_state]
    has_ovs_capability = nm.ovs.CAPABILITY in capabilities
    for iface_type in ifaces_types:
        is_ovs_type = iface_type in (
            nm.ovs.BRIDGE_TYPE,
            nm.ovs.PORT_TYPE,
            nm.ovs.INTERNAL_INTERFACE_TYPE,
        )
        if is_ovs_type and not has_ovs_capability:
            raise NmstateDependencyError(
                "Open vSwitch NetworkManager support not installed "
                "and started"
            )


def validate_interfaces_state(desired_state, current_state):
    validate_link_aggregation_state(desired_state, current_state)


def validate_link_aggregation_state(desired_state, current_state):
    available_ifaces = {
        ifname
        for ifname, ifstate in six.viewitems(desired_state.interfaces)
        if ifstate.get('state') != 'absent'
    }
    available_ifaces |= set(current_state.interfaces)

    specified_slaves = set()
    for iface_state in six.viewvalues(desired_state.interfaces):
        if iface_state.get('state') != 'absent':
            link_aggregation = iface_state.get('link-aggregation')
            if link_aggregation:
                slaves = set(link_aggregation.get('slaves', []))
                if not (slaves <= available_ifaces):
                    raise NmstateValueError(
                        "Link aggregation has missing slave: {}".format(
                            iface_state
                        )
                    )
                if slaves & specified_slaves:
                    raise NmstateValueError(
                        "Link aggregation has reused slave: {}".format(
                            iface_state
                        )
                    )
                specified_slaves |= slaves


def validate_dhcp(state):
    for iface_state in state[Constants.INTERFACES]:
        for family in ('ipv4', 'ipv6'):
            ip = iface_state.get(family, {})
            if (
                ip.get(InterfaceIP.ENABLED)
                and ip.get(InterfaceIP.ADDRESS)
                and (
                    ip.get(InterfaceIP.DHCP) or ip.get(InterfaceIPv6.AUTOCONF)
                )
            ):
                logging.warning(
                    '%s addresses are ignored when ' 'dynamic IP is enabled',
                    family,
                )


def validate_dns(state):
    """
    Only support at most 2 name servers now:
    https://nmstate.atlassian.net/browse/NMSTATE-220
    """
    dns_servers = (
        state.get(DNS.KEY, {}).get(DNS.CONFIG, {}).get(DNS.SERVER, [])
    )
    if len(dns_servers) > 2:
        raise NmstateNotImplementedError(
            'Nmstate only support at most 2 DNS name servers'
        )


def validate_routes(desired_state, current_state):
    """
    A route has several requirements it must comply with:
    - Next-hop interface must be provided
    - The next-hop interface must:
        - Exist and be up (no down/absent)
        - Have the relevant IPv4/6 stack enabled.
    """
    for iface_name, routes in six.viewitems(desired_state.config_iface_routes):
        if not routes:
            continue

        desired_iface_state = desired_state.interfaces.get(iface_name)
        current_iface_state = current_state.interfaces.get(iface_name)
        if desired_iface_state or current_iface_state:
            _assert_iface_is_up(desired_iface_state, current_iface_state)
            if any(is_ipv6_address(route.destination) for route in routes):
                _assert_iface_ipv6_enabled(
                    desired_iface_state, current_iface_state
                )
            if any(not is_ipv6_address(route.destination) for route in routes):
                _assert_iface_ipv4_enabled(
                    desired_iface_state, current_iface_state
                )
        else:
            raise NmstateRouteWithNoInterfaceError(str(routes))


def _assert_iface_is_up(desired_iface_state, current_iface_state):
    """
    Validates that the interface has an UP state.
    Prioritize the desired state over the current state.
    """
    if desired_iface_state:
        state = desired_iface_state.get(schema.Interface.STATE)
        if state is not None:
            if state == schema.InterfaceState.UP:
                return
            raise NmstateRouteWithNoUpInterfaceError(desired_iface_state)
    if current_iface_state:
        state = current_iface_state.get(schema.Interface.STATE)
        if state != schema.InterfaceState.UP:
            raise NmstateRouteWithNoUpInterfaceError(current_iface_state)


def _assert_iface_ipv4_enabled(desired_iface_state, current_iface_state):
    _assert_iface_ip_enabled(
        desired_iface_state, current_iface_state, schema.Interface.IPV4
    )


def _assert_iface_ipv6_enabled(desired_iface_state, current_iface_state):
    _assert_iface_ip_enabled(
        desired_iface_state, current_iface_state, schema.Interface.IPV6
    )


def _assert_iface_ip_enabled(desired_iface_state, current_iface_state, ipkey):
    """
    Validates that the interface has IPv4/6 (ipkey) enabled.
    Prioritize the desired state over the current state.
    """
    if desired_iface_state:
        ip_state = desired_iface_state.get(ipkey)
        if ip_state is not None:
            ip_enabled = ip_state.get(InterfaceIP.ENABLED)
            if ip_enabled is True:
                return
            elif ip_enabled is False:
                raise NmstateRouteWithNoIPInterfaceError(desired_iface_state)
    if current_iface_state:
        ip_state = current_iface_state.get(ipkey)
        if not ip_state.get(InterfaceIP.ENABLED):
            raise NmstateRouteWithNoIPInterfaceError(current_iface_state)
