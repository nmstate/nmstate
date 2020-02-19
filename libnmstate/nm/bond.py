#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

import os
import glob
import re

from . import nmclient
from libnmstate.error import NmstateValueError


BOND_TYPE = "bond"

SYSFS_EMPTY_VALUE = ""

NM_SUPPORTED_BOND_OPTIONS = nmclient.NM.SettingBond.get_valid_options(
    nmclient.NM.SettingBond.new()
)


def create_setting(options):
    bond_setting = nmclient.NM.SettingBond.new()
    for option_name, option_value in options.items():
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
    options = {}
    for sysfs_file in glob.iglob(f"/sys/class/net/{ifname}/bonding/*"):
        option = os.path.basename(sysfs_file)
        if option in NM_SUPPORTED_BOND_OPTIONS:
            options[option] = _read_sysfs_file(sysfs_file)
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
