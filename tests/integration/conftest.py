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

import logging

import pytest

import libnmstate

from .testlib import statelib
from .testlib.statelib import INTERFACES


@pytest.fixture(scope='session', autouse=True)
def logging_setup():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
    )


@pytest.fixture(scope='session', autouse=True)
def ethx_init(preserve_old_config):
    """ Remove any existing definitions on the ethX interfaces. """
    _set_eth_admin_state('eth1', 'down')
    _set_eth_admin_state('eth2', 'down')


@pytest.fixture(scope='function')
def eth1_up():
    _set_eth_admin_state('eth1', 'up')
    try:
        yield statelib.show_only(('eth1',))
    finally:
        _set_eth_admin_state('eth1', 'down')


@pytest.fixture(scope='function')
def eth2_up():
    _set_eth_admin_state('eth2', 'up')
    try:
        yield statelib.show_only(('eth2',))
    finally:
        _set_eth_admin_state('eth2', 'down')


port0_up = eth1_up
port1_up = eth2_up


def _set_eth_admin_state(ifname, state):
    current_state = statelib.show_only((ifname,))
    iface_current_state, = current_state[INTERFACES]
    if iface_current_state['state'] != state or state == 'down':
        desired_state = {
            INTERFACES: [
                {
                    'name': iface_current_state['name'],
                    'type': iface_current_state['type'],
                    'state': state,
                }
            ]
        }
        libnmstate.apply(desired_state)


@pytest.fixture(scope='session', autouse=True)
def preserve_old_config():
    old_state = libnmstate.show()
    yield
    libnmstate.apply(old_state, verify_change=False)
