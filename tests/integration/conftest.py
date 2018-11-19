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

from .testlib import statelib
from .testlib.statelib import INTERFACES


@pytest.fixture(scope='session', autouse=True)
def logging_setup():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG)


@pytest.fixture(scope='function')
def eth1_down():
    _set_eth_admin_state('eth1', 'down')


@pytest.fixture(scope='function')
def eth2_down():
    _set_eth_admin_state('eth2', 'down')


@pytest.fixture(scope='function')
def eth1_up(eth1_down):
    _set_eth_admin_state('eth1', 'up')


@pytest.fixture(scope='function')
def eth2_up(eth2_down):
    _set_eth_admin_state('eth2', 'up')


def _set_eth_admin_state(ifname, state):
    current_state = statelib.show_only((ifname,))
    iface_current_state, = current_state[INTERFACES]
    if iface_current_state['state'] != state:
        desired_state = {INTERFACES: [{'name': iface_current_state['name'],
                                       'type': iface_current_state['type'],
                                       'state': state}]}
        # FIXME: On most systems, IPv6 cannot be disabled by NMState/NM.
        if state == 'up':
            desired_state[INTERFACES][0].update({'ipv6': {'enabled': True}})
        netapplier.apply(desired_state)
