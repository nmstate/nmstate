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

from operator import attrgetter
import os

from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB

from .base_iface import NisporPluginBaseIface
from .bridge_port_vlan import get_port_vlan_info

OPT = LB.Options


NISPOR_USER_HZ_KEYS = [
    "forward_delay",
    "ageing_time",
    "hello_time",
    "max_age",
]


NISPOR_MULTICAST_ROUTERS_INT_MAP = {
    "disabled": 0,
    "temp_query": 1,
    "perm": 2,
    "temp": 3,
}

LSM_BRIDGE_OPTIONS_2_NISPOR = {
    OPT.MAC_AGEING_TIME: "ageing_time",
    OPT.GROUP_FORWARD_MASK: "group_fwd_mask",
    OPT.MULTICAST_SNOOPING: "multicast_snooping",
    OPT.HELLO_TIMER: "hello_timer",
    OPT.GC_TIMER: "gc_timer",
    OPT.MULTICAST_ROUTER: "multicast_router",
    OPT.GROUP_ADDR: "group_addr",
    OPT.HASH_MAX: "multicast_hash_max",
    OPT.MULTICAST_LAST_MEMBER_COUNT: "multicast_last_member_count",
    OPT.MULTICAST_LAST_MEMBER_INTERVAL: "multicast_last_member_interval",
    OPT.MULTICAST_QUERIER: "multicast_querier",
    OPT.MULTICAST_QUERIER_INTERVAL: "multicast_querier_interval",
    OPT.MULTICAST_QUERY_USE_IFADDR: "multicast_query_use_ifaddr",
    OPT.MULTICAST_QUERY_INTERVAL: "multicast_query_interval",
    OPT.MULTICAST_QUERY_RESPONSE_INTERVAL: "multicast_query_response_interval",
    OPT.MULTICAST_STARTUP_QUERY_COUNT: "multicast_startup_query_count",
    OPT.MULTICAST_STARTUP_QUERY_INTERVAL: "multicast_startup_query_interval",
}


LSM_BRIDGE_STP_OPTIONS_2_NISPOR = {
    LB.STP.ENABLED: "stp_state",
    LB.STP.PRIORITY: "priority",
    LB.STP.FORWARD_DELAY: "forward_delay",
    LB.STP.HELLO_TIME: "hello_time",
    LB.STP.MAX_AGE: "max_age",
}


class NisporPluginBridgeIface(NisporPluginBaseIface):
    def __init__(self, np_iface, np_ports):
        super().__init__(np_iface)
        self._np_ports = np_ports

    @property
    def type(self):
        return InterfaceType.LINUX_BRIDGE

    def _options_to_dict(self):
        np_options = self._np_iface.options
        info = _get_nispor_options(LSM_BRIDGE_OPTIONS_2_NISPOR, np_options)
        info[LB.STP_SUBTREE] = _get_nispor_options(
            LSM_BRIDGE_STP_OPTIONS_2_NISPOR, np_options
        )
        return info

    def _ports_to_dict(self):
        info = []
        for np_port in sorted(self._np_ports, key=attrgetter("name")):
            np_sub = np_port.subordinate_state
            port_info = {
                LB.Port.NAME: np_port.name,
                LB.Port.STP_HAIRPIN_MODE: np_sub.hairpin_mode,
                LB.Port.STP_PATH_COST: np_sub.stp_path_cost,
                LB.Port.STP_PRIORITY: np_sub.stp_priority,
            }
            if self._np_iface.options.get("vlan_filtering") and np_sub.vlans:
                port_info[LB.Port.VLAN_SUBTREE] = get_port_vlan_info(np_sub)

            info.append(port_info)
        return info

    def to_dict(self, config_only):
        info = super().to_dict(config_only)
        info[LB.CONFIG_SUBTREE] = {
            LB.OPTIONS_SUBTREE: self._options_to_dict(),
            LB.PORT_SUBTREE: self._ports_to_dict(),
        }
        return info


# Some keys nispor is showing as human readable value, while lsm need integer
# TODO: Use better approach after https://github.com/nispor/nispor/issues/11
def _nispor_value_to_lsm(np_name, np_value):
    """
    Return None if convertion failed.
    Return original value is convertion is not required
    """
    value = np_value
    if np_name == "multicast_router":
        value = NISPOR_MULTICAST_ROUTERS_INT_MAP.get(np_value)
    elif np_name == "stp_state":
        value = np_value in ("kernel_stp", "user_stp")
    elif np_name == "group_addr":
        value = value.upper()
    return value


def _get_nispor_options(np_prop_map, np_options):
    user_hz = os.sysconf("SC_CLK_TCK")
    info = {}
    for key, np_prop_name in np_prop_map.items():
        if np_prop_name in np_options:
            value = _nispor_value_to_lsm(
                np_prop_name, np_options[np_prop_name]
            )
            if value is None:
                continue
            if np_prop_name in NISPOR_USER_HZ_KEYS:
                value = int(value / user_hz)
            info[key] = value
    return info
