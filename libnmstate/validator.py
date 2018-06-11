#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

import jsonschema as js

from . import schema


class LinkAggregationSlavesMissingError(Exception):
    pass


class LinkAggregationSlavesReuseError(Exception):
    pass


def verify(data, validation_schema=schema.ifaces_schema):
    js.validate(data, validation_schema)


def verify_interfaces_state(ifaces_state, ifaces_desired_state):
    verify_link_aggregation_state(ifaces_state, ifaces_desired_state)


def verify_link_aggregation_state(ifaces_state, ifaces_desired_state):
    available_ifaces = {iface_state['name'] for iface_state in ifaces_state}
    available_ifaces |= {
        iface_name for iface_name in ifaces_desired_state
        if ifaces_desired_state[iface_name].get('state') != 'absent'
    }
    specified_slaves = set()
    for iface_state in ifaces_state:
        link_aggregation = iface_state.get('link-aggregation')
        if link_aggregation:
            slaves = set(link_aggregation.get('slaves', []))
            if not (slaves <= available_ifaces):
                raise LinkAggregationSlavesMissingError(iface_state)
            if slaves & specified_slaves:
                raise LinkAggregationSlavesReuseError(iface_state)
            specified_slaves |= slaves
