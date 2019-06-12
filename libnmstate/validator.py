#
# Copyright 2018-2019 Red Hat, Inc.
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

import logging
import six

import jsonschema as js

from . import nm
from . import schema
from .schema import Constants
from libnmstate.schema import DNS
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError


def validate(data, validation_schema=schema.ifaces_schema):
    js.validate(data, validation_schema)


def validate_capabilities(state, capabilities):
    validate_interface_capabilities(state[Constants.INTERFACES], capabilities)


def validate_interface_capabilities(ifaces_state, capabilities):
    ifaces_types = [iface_state['type'] for iface_state in ifaces_state]
    has_ovs_capability = nm.ovs.CAPABILITY in capabilities
    for iface_type in ifaces_types:
        is_ovs_type = iface_type in (
            nm.ovs.BRIDGE_TYPE,
            nm.ovs.PORT_TYPE,
            nm.ovs.INTERNAL_INTERFACE_TYPE
        )
        if is_ovs_type and not has_ovs_capability:
            raise NmstateDependencyError(
                "Open vSwitch NetworkManager support not installed "
                "and started")


def validate_interfaces_state(desired_state, current_state):
    validate_link_aggregation_state(desired_state, current_state)


def validate_link_aggregation_state(desired_state, current_state):
    available_ifaces = {
        ifname for ifname, ifstate in six.viewitems(desired_state.interfaces)
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
                            iface_state))
                if slaves & specified_slaves:
                    raise NmstateValueError(
                        "Link aggregation has reused slave: {}".format(
                            iface_state))
                specified_slaves |= slaves


def validate_dhcp(state):
    for iface_state in state[Constants.INTERFACES]:
        for family in ('ipv4', 'ipv6'):
            ip = iface_state.get(family, {})
            if ip.get('enabled') and ip.get('address') and \
               (ip.get('dhcp') or ip.get('autoconf')):
                logging.warning('%s addresses are ignored when '
                                'dynamic IP is enabled', family)


def validate_dns(state):
    """
    Only support at most 2 name servers now:
    https://nmstate.atlassian.net/browse/NMSTATE-220
    """
    dns_servers = state.get(
        DNS.KEY, {}).get(DNS.CONFIG, {}).get(DNS.SERVER, [])
    if len(dns_servers) > 2:
        raise NmstateNotImplementedError(
            'Nmstate only support at most 2 DNS name servers')
