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

import contextlib
import os
import glob
import re

from . import nmclient
from libnmstate.error import NmstateValueError
from libnmstate.appliers.bond import is_in_mac_restricted_mode


BOND_TYPE = "bond"

SYSFS_EMPTY_VALUE = ""

NM_SUPPORTED_BOND_OPTIONS = nmclient.NM.SettingBond.get_valid_options(
    nmclient.NM.SettingBond.new()
)


def create_setting(options, wired_setting):
    bond_setting = nmclient.NM.SettingBond.new()
    for option_name, option_value in options.items():
        if wired_setting and is_in_mac_restricted_mode(options):
            # When in MAC restricted mode, MAC address should be unset.
            wired_setting.props.cloned_mac_address = None
        if option_value != SYSFS_EMPTY_VALUE:
            success = bond_setting.add_option(option_name, str(option_value))
            if not success:
                raise NmstateValueError(
                    "Invalid bond option: '{}'='{}'".format(
                        option_name, option_value
                    )
                )

    return bond_setting


def is_bond_type_id(type_id):
    return type_id == nmclient.NM.DeviceType.BOND


def get_bond_info(nm_device):
    slaves = get_slaves(nm_device)
    options = _get_options(nm_device)
    if slaves or options:
        return {"slaves": slaves, "options": options}
    else:
        return {}


def _get_options(nm_device):
    ifname = nm_device.get_iface()
    bond_setting = nmclient.NM.SettingBond.new()
    bond_option_names_in_profile = get_bond_option_names_in_profile(nm_device)
    options = {}
    for sysfs_file in glob.iglob(f"/sys/class/net/{ifname}/bonding/*"):
        option = os.path.basename(sysfs_file)
        if option in NM_SUPPORTED_BOND_OPTIONS:
            value = _read_sysfs_file(sysfs_file)
            if (
                option == "mode"
                or value != bond_setting.get_option_default(option)
                # Always include bond options which are explicitly defined in
                # on-disk profile.
                or option in bond_option_names_in_profile
            ):
                if option == "arp_ip_target":
                    value = value.replace(" ", ",")
                options[option] = value
    # Workaround of https://bugzilla.redhat.com/show_bug.cgi?id=1806549
    if "miimon" not in options:
        options["miimon"] = bond_setting.get_option_default("miimon")
    return options


def _read_sysfs_file(file_path):
    with open(file_path) as fd:
        return _strip_sysfs_name_number_value(fd.read().rstrip("\n"))


def _strip_sysfs_name_number_value(value):
    """
    In sysfs/kernel, the value of some are shown with both human friendly
    string and integer. For example, bond mode in sysfs is shown as
    'balance-rr 0'. This function only return the human friendly string.
    """
    return re.sub(" [0-9]$", "", value)


def get_slaves(nm_device):
    return nm_device.get_slaves()


def get_bond_option_names_in_profile(nm_device):
    ac = nm_device.get_active_connection()
    with contextlib.suppress(AttributeError):
        bond_setting = ac.get_connection().get_setting_bond()
        return {
            bond_setting.get_option(i)[1]
            for i in range(0, bond_setting.get_num_options())
        }
    return set()
