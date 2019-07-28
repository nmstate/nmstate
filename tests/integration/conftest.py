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

from .testlib import ifacelib


@pytest.fixture(scope='session', autouse=True)
def logging_setup():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
    )


@pytest.fixture(scope='session', autouse=True)
def ethx_init(preserve_old_config):
    """ Remove any existing definitions on the ethX interfaces. """
    ifacelib.ifaces_init('eth1', 'eth2')


@pytest.fixture(scope='function')
def eth1_up():
    with ifacelib.iface_up('eth1') as ifstate:
        yield ifstate


@pytest.fixture(scope='function')
def eth2_up():
    with ifacelib.iface_up('eth2') as ifstate:
        yield ifstate


port0_up = eth1_up
port1_up = eth2_up


@pytest.fixture(scope='session', autouse=True)
def preserve_old_config():
    old_state = libnmstate.show()
    yield
    libnmstate.apply(old_state, verify_change=False)
