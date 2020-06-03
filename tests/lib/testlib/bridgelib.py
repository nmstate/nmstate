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
from libnmstate.schema import LinuxBridge as LB

from .ifacelib import gen_foo_iface_info
from .constants import SLAVE1_IFACE_NAME
from .constants import SLAVE2_IFACE_NAME

Port = LB.Port
Vlan = LB.Port.Vlan

LINUX_BRIDGE_IFACE_NAME = "linux-br0"

SLAVE1_PORT_CONFIG = {
    Port.NAME: SLAVE1_IFACE_NAME,
    Port.STP_HAIRPIN_MODE: False,
    Port.STP_PATH_COST: 100,
    Port.STP_PRIORITY: 32,
}

SLAVE1_VLAN_CONFIG_ACCESS = {
    Vlan.MODE: Vlan.Mode.ACCESS,
    Vlan.TAG: 305,
}

SLAVE2_PORT_CONFIG = {
    Port.NAME: SLAVE2_IFACE_NAME,
    Port.STP_HAIRPIN_MODE: False,
    Port.STP_PATH_COST: 100,
    Port.STP_PRIORITY: 32,
}

TRUNK_TAGS_IDS = [{Vlan.TrunkTags.ID: 101}, {Vlan.TrunkTags.ID: 102}]
TRUNK_TAGS_ID_RANGES = [
    {
        Vlan.TrunkTags.ID_RANGE: {
            Vlan.TrunkTags.MIN_RANGE: 400,
            Vlan.TrunkTags.MAX_RANGE: 500,
        }
    },
    {
        Vlan.TrunkTags.ID_RANGE: {
            Vlan.TrunkTags.MIN_RANGE: 600,
            Vlan.TrunkTags.MAX_RANGE: 900,
        }
    },
]

SLAVE2_VLAN_CONFIG_TRUNK_WITH_ID_RANGE = {
    Vlan.MODE: Vlan.Mode.TRUNK,
    Vlan.TAG: 105,
    Vlan.ENABLE_NATIVE: True,
    Vlan.TRUNK_TAGS: TRUNK_TAGS_ID_RANGES,
}

SLAVE2_VLAN_CONFIG_TRUNK_WITH_ID = {
    Vlan.MODE: Vlan.Mode.TRUNK,
    Vlan.TAG: 105,
    Vlan.ENABLE_NATIVE: True,
    Vlan.TRUNK_TAGS: TRUNK_TAGS_IDS,
}

SLAVE2_VLAN_CONFIG_TRUNK = SLAVE2_VLAN_CONFIG_TRUNK_WITH_ID

TEST_SLAVE_PORT_CONFIGS = [SLAVE1_PORT_CONFIG, SLAVE2_PORT_CONFIG]

TEST_SLAVE_NAMES = [SLAVE1_IFACE_NAME, SLAVE2_IFACE_NAME]


def gen_bridge_iface_info():
    iface_info = gen_foo_iface_info(iface_type=InterfaceType.LINUX_BRIDGE)
    iface_info[Interface.NAME] = LINUX_BRIDGE_IFACE_NAME
    iface_info[LB.CONFIG_SUBTREE] = {
        LB.PORT_SUBTREE: deepcopy(TEST_SLAVE_PORT_CONFIGS),
        LB.OPTIONS_SUBTREE: {
            LB.Options.GROUP_FORWARD_MASK: 0,
            LB.Options.MAC_AGEING_TIME: 300,
            LB.Options.MULTICAST_SNOOPING: True,
            LB.STP_SUBTREE: {
                LB.STP.ENABLED: False,
                LB.STP.FORWARD_DELAY: 15,
                LB.STP.HELLO_TIME: 2,
                LB.STP.MAX_AGE: 20,
                LB.STP.PRIORITY: 32768,
            },
        },
    }
    return iface_info


def gen_bridge_iface_info_with_vlan_filter():
    iface_info = gen_bridge_iface_info()
    br_config = iface_info[LB.CONFIG_SUBTREE]
    br_config[LB.PORT_SUBTREE][0][Port.VLAN_SUBTREE] = deepcopy(
        SLAVE1_VLAN_CONFIG_ACCESS
    )
    br_config[LB.PORT_SUBTREE][1][Port.VLAN_SUBTREE] = deepcopy(
        SLAVE2_VLAN_CONFIG_TRUNK
    )
    return iface_info
