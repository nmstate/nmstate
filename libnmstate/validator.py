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
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateValueError


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
            raise NmstateDependencyError(
                "Open vSwitch NetworkManager support not installed "
                "and started")


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
                    raise NmstateValueError(
                        "Link aggregation has missing slave: {}".format(
                            iface_state))
                if slaves & specified_slaves:
                    raise NmstateValueError(
                        "Link aggregation has reused slave: {}".format(
                            iface_state))
                specified_slaves |= slaves


def verify_dhcp(state):
    for iface_state in state[Constants.INTERFACES]:
        for family in ('ipv4', 'ipv6'):
            ip = iface_state.get(family, {})
            if ip.get('enabled') and ip.get('address') and \
               (ip.get('dhcp') or ip.get('autoconf')):
                logging.warning('%s addresses are ignored when '
                                'dynamic IP is enabled', family)
