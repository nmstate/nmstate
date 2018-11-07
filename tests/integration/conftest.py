#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import logging

import pytest

from libnmstate import netapplier
from libnmstate import sysctl

from .testlib import cmd
from .testlib import statelib
from .testlib.statelib import INTERFACES


@pytest.fixture(scope='session', autouse=True)
def logging_setup():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG)


@pytest.fixture(scope='session', autouse=True)
def init_nm_test_interfaces():
    """
    Initialize the test interfaces in order to properly operate with existing
    NetworkManager limitation regarding IPv6 stack.
    NM is learning the initial IPv6 stack state for an interface when the
    interfaces is first managed. Therefore, this function makes sure the
    learned state is IPv6 disabled so NM will return the interfaces to this
    state when marked with IPv6 method=ignore.

    FIXME: This special handling should be dropped when either NM fixes its
    behaviour or an explicit disable_ipv6=1 is executed by nmstate.
    """
    for ifname in ('eth1', 'eth2'):
        is_ipv6_disabled = sysctl.is_ipv6_disabled(ifname)
        cmd.exec_cmd(('nmcli', 'device', 'set', ifname, 'managed', 'no'))
        sysctl.disable_ipv6(ifname)
        cmd.exec_cmd(('nmcli', 'device', 'set', ifname, 'managed', 'yes'))
        if not is_ipv6_disabled:
            sysctl.enable_ipv6(ifname)


@pytest.fixture(scope='function', autouse=True)
def cleanup_test_interfaces():
    ifaces_down_state = {
        INTERFACES: []
    }
    current_state = statelib.show_only(('eth1', 'eth2'))
    for iface_state in current_state[INTERFACES]:
        if iface_state['state'] == 'up':
            ifaces_down_state[INTERFACES].append(
                {
                    'name': iface_state['name'],
                    'type': iface_state['type'],
                    'state': 'down'
                }
            )

    if ifaces_down_state[INTERFACES]:
        netapplier.apply(ifaces_down_state)
