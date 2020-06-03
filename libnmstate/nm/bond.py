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

from libnmstate.error import NmstateValueError
from libnmstate.ifaces.bond import BondIface
from libnmstate.schema import Bond
from .common import NM


BOND_TYPE = "bond"

SYSFS_EMPTY_VALUE = ""

NM_SUPPORTED_BOND_OPTIONS = NM.SettingBond.get_valid_options(
    NM.SettingBond.new()
)

SYSFS_BOND_OPTION_FOLDER_FMT = "/sys/class/net/{ifname}/bonding"


def create_setting(options, wired_setting):
    bond_setting = NM.SettingBond.new()
    _fix_bond_option_arp_interval(options)
    for option_name, option_value in options.items():
        if wired_setting and BondIface.is_mac_restricted_mode(
            options.get(Bond.MODE), options
        ):
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
    return type_id == NM.DeviceType.BOND


def get_bond_info(nm_device):
    slaves = get_slaves(nm_device)
    options = _get_options(nm_device)
    if slaves or options:
        return {"slaves": slaves, "options": options}
    else:
        return {}


def _get_options(nm_device):
    ifname = nm_device.get_iface()
    bond_option_names_in_profile = get_bond_option_names_in_profile(nm_device)
    if (
        "miimon" in bond_option_names_in_profile
        or "arp_interval" in bond_option_names_in_profile
    ):
        bond_option_names_in_profile.add("arp_interval")
        bond_option_names_in_profile.add("miimon")

    # Mode is required
    sysfs_folder = SYSFS_BOND_OPTION_FOLDER_FMT.format(ifname=ifname)
    mode = _read_sysfs_file(f"{sysfs_folder}/mode")

    bond_setting = NM.SettingBond.new()
    bond_setting.add_option(Bond.MODE, mode)

    options = {Bond.MODE: mode}
    for sysfs_file in glob.iglob(f"{sysfs_folder}/*"):
        option = os.path.basename(sysfs_file)
        if option in NM_SUPPORTED_BOND_OPTIONS:
            value = _read_sysfs_file(sysfs_file)
            # When default_value is None, it means this option is invalid
            # under this bond mode
            default_value = bond_setting.get_option_default(option)
            if (
                (default_value and value != default_value)
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


def _fix_bond_option_arp_interval(bond_options):
    """
    Due to bug https://bugzilla.redhat.com/show_bug.cgi?id=1806549
    NM 1.22.8 treat 'arp_interval 0' as arp_interval enabled(0 actual means
    disabled), which then conflict with 'miimon'.
    The workaround is remove 'arp_interval 0' when 'miimon' > 0.
    """
    if "miimon" in bond_options and "arp_interval" in bond_options:
        try:
            miimon = int(bond_options["miimon"])
            arp_interval = int(bond_options["arp_interval"])
        except ValueError as e:
            raise NmstateValueError(f"Invalid bond option: {e}")
        if miimon > 0 and arp_interval == 0:
            bond_options.pop("arp_interval")
            bond_options.pop("arp_ip_target", None)
