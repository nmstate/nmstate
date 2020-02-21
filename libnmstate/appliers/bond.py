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
from libnmstate.schema import BondMode


def get_bond_slaves_from_state(iface_state, default=()):
    return iface_state.get(Bond.CONFIG_SUBTREE, {}).get(Bond.SLAVES, default)


def is_in_mac_restricted_mode(bond_options):
    """
    Return True when Bond option does not allow MAC address defined.
    In MAC restricted mode means:
        Bond mode is BondMode.ACTIVE_BACKUP
        Bond option "fail_over_mac" is active.
    """
    return BondMode.ACTIVE_BACKUP == bond_options.get(
        Bond.MODE
    ) and bond_options.get("fail_over_mac") in ("1", 1, "active",)
