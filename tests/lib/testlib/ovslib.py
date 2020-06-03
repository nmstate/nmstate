#
# Copyright (c) 2020 Red Hat, Inc.
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

from copy import deepcopy

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge

from .ifacelib import gen_foo_iface_info
from .constants import SLAVE1_IFACE_NAME
from .constants import SLAVE2_IFACE_NAME

OVS_BRIDGE_IFACE_NAME = "ovs-br0"
OVS_IFACE_NAME = "ovs0"

SLAVE_PORT_CONFIGS = [
    {OVSBridge.Port.NAME: SLAVE1_IFACE_NAME},
    {OVSBridge.Port.NAME: SLAVE2_IFACE_NAME},
    {OVSBridge.Port.NAME: OVS_IFACE_NAME},
]


def gen_ovs_bridge_info():
    iface_info = gen_foo_iface_info(iface_type=InterfaceType.OVS_BRIDGE)
    iface_info[Interface.NAME] = OVS_BRIDGE_IFACE_NAME
    iface_info[OVSBridge.CONFIG_SUBTREE] = {
        OVSBridge.PORT_SUBTREE: deepcopy(SLAVE_PORT_CONFIGS),
        OVSBridge.OPTIONS_SUBTREE: {},
    }
    return iface_info
