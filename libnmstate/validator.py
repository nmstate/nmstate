#
# Copyright (c) 2018-2020 Red Hat, Inc.
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

import jsonschema as js

from libnmstate.schema import Interface
from libnmstate.schema import OvsDB
from libnmstate.schema import InterfaceType
from libnmstate.error import NmstateDependencyError

from . import schema
from .plugin import NmstatePlugin

MAX_SUPPORTED_INTERFACES = 1000


def schema_validate(data, validation_schema=schema.ifaces_schema):
    data = copy.deepcopy(data)
    _validate_max_supported_intface_count(data)
    for ifstate in data.get(schema.Interface.KEY, ()):
        if not ifstate.get(schema.Interface.TYPE):
            ifstate[schema.Interface.TYPE] = schema.InterfaceType.UNKNOWN
    js.validate(data, validation_schema)


def validate_capabilities(state, capabilities):
    validate_interface_capabilities(state.get(Interface.KEY, []), capabilities)
    validate_ovsdb_global_cap(state.get(OvsDB.KEY, {}), capabilities)


def validate_interface_capabilities(ifaces_state, capabilities):
    ifaces_types = {iface_state.get("type") for iface_state in ifaces_state}
    has_ovs_capability = NmstatePlugin.OVS_CAPABILITY in capabilities
    has_team_capability = NmstatePlugin.TEAM_CAPABILITY in capabilities
    for iface_type in ifaces_types:
        is_ovs_type = iface_type in (
            InterfaceType.OVS_BRIDGE,
            InterfaceType.OVS_INTERFACE,
            InterfaceType.OVS_PORT,
        )
        if is_ovs_type and not has_ovs_capability:
            raise NmstateDependencyError(
                "Open vSwitch support not properly installed or started"
            )
        elif iface_type == InterfaceType.TEAM and not has_team_capability:
            raise NmstateDependencyError(
                "Team support not properly installed or started"
            )


def _validate_max_supported_intface_count(data):
    """
    Raises warning if the interfaces count in the single desired state
    exceeds the limit specified in MAX_SUPPORTED_INTERFACES
    """
    num_of_interfaces = len(
        [intface for intface in data.get(schema.Interface.KEY, ())]
    )
    if num_of_interfaces > MAX_SUPPORTED_INTERFACES:
        logging.warning(
            "Interfaces count exceeds the limit %s in desired state",
            MAX_SUPPORTED_INTERFACES,
        )


def validate_ovsdb_global_cap(ovsdb_global_conf, capabilities):
    if (
        ovsdb_global_conf
        and NmstatePlugin.PLUGIN_CAPABILITY_OVSDB_GLOBAL not in capabilities
    ):
        raise NmstateDependencyError(
            "Missing plugin for ovs-db global configuration, "
            "please try to install 'nmstate-plugin-ovsdb' or other plugin "
            "provides NmstatePlugin.PLUGIN_CAPABILITY_OVSDB_GLOBAL"
        )
