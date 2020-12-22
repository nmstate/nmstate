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

from libnmstate.schema import Bond
from libnmstate.schema import InterfaceType

from .base_iface import NisporPluginBaseIface

SUPPORTED_BOND_OPTIONS = (
    "ad_actor_sys_prio",
    "ad_actor_system",
    "ad_select",
    "ad_user_port_key",
    "all_subordinates_active",
    "arp_all_targets",
    "arp_interval",
    "arp_ip_target",
    "arp_validate",
    "downdelay",
    "fail_over_mac",
    "lacp_rate",
    "lp_interval",
    "miimon",
    "min_links",
    "num_grat_arp",
    "num_unsol_na",
    "packets_per_subordinate",
    "primary",
    "primary_reselect",
    "resend_igmp",
    "tlb_dynamic_lb",
    "updelay",
    "use_carrier",
    "xmit_hash_policy",
)


class NisporPluginBondIface(NisporPluginBaseIface):
    @property
    def type(self):
        return InterfaceType.BOND

    def to_dict(self, config_only):
        info = super().to_dict(config_only)
        info[Bond.CONFIG_SUBTREE] = {
            Bond.MODE: self._np_iface.mode,
            Bond.PORT: self._np_iface.subordinates,
            Bond.OPTIONS_SUBTREE: {},
        }
        bond_opts = info[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE]
        for opt_name in SUPPORTED_BOND_OPTIONS:
            value = getattr(self._np_iface, opt_name)
            if opt_name == "all_subordinates_active":
                # The sysfs is using `all_slave_active` name
                opt_name = "all_slaves_active"
            elif opt_name == "packets_per_subordinate":
                opt_name = "packets_per_slave"
            if value is not None:
                bond_opts[opt_name] = value
        return info
