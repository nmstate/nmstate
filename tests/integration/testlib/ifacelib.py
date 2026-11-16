# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import libnmstate
from libnmstate import schema

from . import statelib
from .cmdlib import exec_cmd


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


def delete_iface_and_profile(ifname):
    """
    Delete an interface and its NM profile.

    The profile is removed first so NM cannot recreate the link from an
    autoconnect profile; nmstate then removes the link and verifies it
    is gone.
    """
    exec_cmd(("nmcli", "c", "del", ifname))
    exec_cmd(("ip", "link", "delete", ifname))
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
