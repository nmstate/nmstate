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

    for ifname in ('eth1', 'eth2'):
        ifaces_up_state = {
            INTERFACES: [
                {
                    'name': ifname,
                    'type': 'ethernet',
                    'state': 'up',
                    'ipv6': {
                        'enabled': True
                    }
                }
            ]
        }
        netapplier.apply(ifaces_up_state)
