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

from libnmstate.error import NmstateNotImplementedError
from libnmstate.error import NmstateValueError
from libnmstate.ifaces.bond import BondIface
from libnmstate.schema import Bond
from libnmstate.state import merge_dict
from .common import NM


BOND_TYPE = "bond"

SYSFS_EMPTY_VALUE = ""

NM_SUPPORTED_BOND_OPTIONS = NM.SettingBond.get_valid_options(
    NM.SettingBond.new()
)

SYSFS_BOND_OPTION_FOLDER_FMT = "/sys/class/net/{ifname}/bonding"

BOND_AD_ACTOR_SYSTEM_USE_BOND_MAC = "00:00:00:00:00:00"


def create_setting(iface, wired_setting, base_con_profile):
    bond_setting = NM.SettingBond.new()
    options = iface.original_desire_dict.get(Bond.CONFIG_SUBTREE, {}).get(
        Bond.OPTIONS_SUBTREE
    )
    mode = iface.bond_mode
    if options != {}:
        if options is None:
            options = {}
        if not iface.is_bond_mode_changed:
            old_bond_options = {}
            if base_con_profile:
                old_bond_options = _get_bond_options_from_profiles(
                    base_con_profile.get_setting_bond()
                )
            merge_dict(options, old_bond_options)
    if mode:
        bond_setting.add_option("mode", mode)
    for option_name, option_value in options.items():
        if wired_setting and BondIface.is_mac_restricted_mode(mode, options):
            # When in MAC restricted mode, MAC address should be unset.
            wired_setting.props.cloned_mac_address = None
        if (
            option_name == "ad_actor_system"
            and option_value == BOND_AD_ACTOR_SYSTEM_USE_BOND_MAC
        ):
            # The all zero ad_actor_system is the kernel default value
            # And it is invalid to set as all zero
            continue
        if option_value != SYSFS_EMPTY_VALUE:
            option_value = _nm_fix_bond_options(option_name, option_value)
            success = bond_setting.add_option(option_name, option_value)
            if not success:
                raise NmstateValueError(
                    "Invalid bond option: '{}'='{}'".format(
                        option_name, option_value
                    )
                )

    return bond_setting


def _nm_fix_bond_options(option_name, option_value):
    if option_name == "all_slaves_active":
        if option_value in ("delivered", "1"):
            option_value = 1
        elif option_value in ("dropped", "0"):
            option_value = 0
        else:
            raise NmstateNotImplementedError(
                "Unsupported bond option: '{}'='{}'".format(
                    option_name, option_value
                )
            )
    elif option_name in ("use_carrier", "tlb_dynamic_lb"):
        option_value = 1 if option_value else 0

    return str(option_value)


def _get_bond_options_from_profiles(bond_setting):
    ret = {}
    if bond_setting:
        for i in range(0, bond_setting.get_num_options()):
            name, value = bond_setting.get_option(i)[1:3]
            if name != "mode":
                ret[name] = value
    return ret
