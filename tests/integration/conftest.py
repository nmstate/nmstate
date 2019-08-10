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
import time

import pytest

import libnmstate

from .testlib import ifacelib
from .testlib.env import TEST_NIC1
from .testlib.env import TEST_NIC2
from .testlib.ifacelib import veth_create


_NIC1_END = "_{}".format(TEST_NIC1)
_NIC2_END = "_{}".format(TEST_NIC2)


@pytest.fixture(scope='session', autouse=True)
def test_env_setup():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
    )
    old_state = libnmstate.show()
    with veth_create(TEST_NIC1, _NIC1_END), veth_create(TEST_NIC2, _NIC2_END):
        yield
    libnmstate.apply(old_state, verify_change=False)


@pytest.fixture(scope='function', autouse=True)
def test_nic_init():
    ifacelib.ifaces_init(TEST_NIC1, TEST_NIC2)


@pytest.fixture(scope='function')
def test_nic1_up():
    with ifacelib.iface_up(TEST_NIC1) as ifstate:
        yield ifstate


@pytest.fixture(scope='function')
def test_nic2_up():
    with ifacelib.iface_up(TEST_NIC2) as ifstate:
        yield ifstate


port0_up = test_nic1_up
port1_up = test_nic2_up
