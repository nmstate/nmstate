# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2019 Red Hat, Inc.
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

from contextlib import contextmanager

import libnmstate
from libnmstate import schema

from . import statelib


def ifaces_init(*ifnames):
    """Remove any existing definitions on the interfaces."""
    for ifname in ifnames:
        _set_eth_admin_state(ifname, schema.InterfaceState.ABSENT)


@contextmanager
def iface_up(ifname):
    _set_eth_admin_state(ifname, schema.InterfaceState.UP)
    try:
        yield statelib.show_only((ifname,))
    finally:
        _set_eth_admin_state(ifname, schema.InterfaceState.ABSENT)


def _set_eth_admin_state(ifname, state):
    libnmstate.apply(
        {
            schema.Interface.KEY: [
                {schema.Interface.NAME: ifname, schema.Interface.STATE: state}
            ]
        }
    )


def get_mac_address(ifname):
    state = statelib.show_only((ifname,))
    return state[schema.Interface.KEY][0].get(schema.Interface.MAC)
