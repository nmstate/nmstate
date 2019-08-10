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
import os

import libnmstate
from libnmstate import schema

from . import statelib
from .cmd import exec_cmd


def ifaces_init(*ifnames):
    """ Remove any existing definitions on the interfaces. """
    for ifname in ifnames:
        _set_eth_admin_state(ifname, schema.InterfaceState.DOWN)


@contextmanager
def iface_up(ifname):
    _set_eth_admin_state(ifname, schema.InterfaceState.UP)
    try:
        yield statelib.show_only((ifname,))
    finally:
        _set_eth_admin_state(ifname, schema.InterfaceState.DOWN)


@contextmanager
def veth_create(ifname, ifname_end):
    """
    Create veth interface named as `ifname` with peer `ifname_end`.
    The `ifname` interface will be managed by nmcli whiel the 'ifname_end' is
    not.
    Firewalld will temporally trust all network flow on `ifname` and
    `ifname_end`.
    """
    _delete_veth(ifname)
    _delete_veth(ifname_end)
    _create_veth(ifname, ifname_end)
    yield
    _delete_veth(ifname)
    _delete_veth(ifname_end)


def _create_veth(ifname, ifname_end):
    assert (
        exec_cmd(
            ['ip', 'link', 'add', ifname, 'type', 'veth', 'peer', ifname_end]
        )[0]
        == 0
    )
    assert exec_cmd(['nmcli', 'd', 'set', ifname, 'managed', 'yes'])[0] == 0
    assert exec_cmd(['ip', 'link', 'set', ifname, 'up'])[0] == 0
    assert exec_cmd(['ip', 'link', 'set', ifname_end, 'up'])[0] == 0
    try:
        exec_cmd(['firewall-cmd', '--zone=trusted', '--add-interface', ifname])
        exec_cmd(
            ['firewall-cmd', '--zone=trusted', '--add-interface', ifname_end]
        )
    except FileNotFoundError:
        pass


def _delete_veth(ifname):
    if os.path.exists('/sys/class/net/{}'.format(ifname)):
        exec_cmd(['ip', 'link', 'del', ifname])
        try:
            exec_cmd(
                [
                    'firewall-cmd',
                    '--zone=trusted',
                    '--remove-interface',
                    ifname,
                ]
            )
        except FileNotFoundError:
            pass


def _set_eth_admin_state(ifname, state):
    current_state = statelib.show_only((ifname,))
    current_ifstate, = current_state[schema.Interface.KEY]
    iface_current_admin_state = current_ifstate[schema.Interface.STATE]
    if (
        iface_current_admin_state != state
        or state == schema.InterfaceState.DOWN
    ):
        desired_state = {
            schema.Interface.KEY: [
                {
                    schema.Interface.NAME: ifname,
                    schema.Interface.STATE: state,
                    # The sysfs disable IPv6 only works if ask specifically.
                    schema.Interface.IPV6: {
                        schema.InterfaceIPv6.ENABLED: False
                    },
                }
            ]
        }
        libnmstate.apply(desired_state)
