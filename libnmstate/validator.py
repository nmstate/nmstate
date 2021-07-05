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

import logging
import re

from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from .plugin import NmstatePlugin

MAX_SUPPORTED_INTERFACES = 1000


def validate_capabilities(state, capabilities):
    validate_interface_capabilities(state.get(Interface.KEY, []), capabilities)


def validate_interface_capabilities(ifaces_state, capabilities):
    ifaces_types = {iface_state.get("type") for iface_state in ifaces_state}
    has_ovs_capability = NmstatePlugin.OVS_CAPABILITY in capabilities
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


def _validate_max_supported_intface_count(data):
    """
    Raises warning if the interfaces count in the single desired state
    exceeds the limit specified in MAX_SUPPORTED_INTERFACES
    """
    num_of_interfaces = len(
        [intface for intface in data.get(Interface.KEY, ())]
    )
    if num_of_interfaces > MAX_SUPPORTED_INTERFACES:
        logging.warning(
            "Interfaces count exceeds the limit %s in desired state",
            MAX_SUPPORTED_INTERFACES,
        )


def validate_string(value, name, valid_values=None, pattern=None):
    if value is None:
        return

    if not isinstance(value, str):
        raise NmstateValueError(
            f"Property {name} with value {value} must be a "
            f"string but is {type(value)}"
        )
    elif valid_values and value not in valid_values:
        raise NmstateValueError(
            f"Property {name} with value {value} is not a valid value from "
            f"the list {valid_values}"
        )
    elif pattern and not re.match(pattern, value):
        raise NmstateValueError(
            f"Property {name} with value {value} does not match the required "
            f"pattern {pattern}"
        )


def validate_boolean(value, name):
    if value is None:
        return

    if not isinstance(value, bool):
        raise NmstateValueError(
            f"Property {name} with value {value} must be a "
            f"boolean but is {type(value)}"
        )


def validate_integer(value, name, minimum=None, maximum=None):
    if value is None:
        return

    # This is required a bool is instance of int.
    if type(value) != int:
        raise NmstateValueError(
            f"Property {name} with value {value} must be an "
            f"integer but is {type(value)}"
        )
    elif minimum is not None and value < minimum:
        raise NmstateValueError(
            f"Property {name} with value {value} must be greater "
            f"than {minimum}"
        )
    elif maximum is not None and value > maximum:
        raise NmstateValueError(
            f"Property {name} with value {value} must be lower "
            f"than {maximum}"
        )


def validate_list(value, name, elem_type=None):
    if value is None:
        return

    if not isinstance(value, list):
        raise NmstateValueError(
            f"Property {name} with value {value} must be a "
            f"list but is {type(value)}"
        )
    elif elem_type is not None:
        match_type = all([isinstance(elem, elem_type) for elem in value])
        if not match_type:
            raise NmstateValueError(
                f"Property {name} with value {value}, all the element must "
                f"be type {elem_type}"
            )
