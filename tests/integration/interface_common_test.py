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
import time

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError

from .testlib import assertlib
from .testlib import cmd as libcmd
from .testlib import statelib
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState

DUMMY_INTERFACE = 'dummy_test'


@pytest.fixture(scope='function')
def ip_link_dummy():
    libcmd.exec_cmd(['ip', 'link', 'add', DUMMY_INTERFACE, 'type', 'dummy'])
    try:
        yield
    finally:
        libcmd.exec_cmd(['ip', 'link', 'del', DUMMY_INTERFACE])


@contextmanager
def dummy_interface(name):
    dummy_desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    libnmstate.apply(dummy_desired_state)
    try:
        yield dummy_desired_state
    finally:
        dummy_state = dummy_desired_state[Interface.KEY][0]
        dummy_state[Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(dummy_desired_state)


def test_iface_description_removal(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.DESCRIPTION] = 'bar'
    libnmstate.apply(desired_state)
    current_state = statelib.show_only(('eth1',))
    assert current_state[Interface.KEY][0][Interface.DESCRIPTION] == 'bar'

    desired_state[Interface.KEY][0][Interface.DESCRIPTION] = ''
    libnmstate.apply(desired_state)
    current_state = statelib.show_only(('eth1',))
    assert Interface.DESCRIPTION not in current_state[Interface.KEY][0]


@pytest.mark.xfail(
    raises=(AssertionError),
    reason='https://nmstate.atlassian.net/browse/NMSTATE-277',
)
def test_take_over_virtual_interface_then_remove(ip_link_dummy):
    with dummy_interface(DUMMY_INTERFACE) as dummy_desired_state:
        assertlib.assert_state_match(dummy_desired_state)

    current_state = statelib.show_only((DUMMY_INTERFACE,))
    assert len(current_state[Interface.KEY]) == 0


def test_take_over_virtual_interface_and_rollback(ip_link_dummy):
    with dummy_interface(DUMMY_INTERFACE) as dummy_desired_state:
        assertlib.assert_state_match(dummy_desired_state)

        dummy_desired_state[Interface.KEY][0]['invalid_key'] = 'foo'
        with pytest.raises(NmstateVerificationError):
            libnmstate.apply(dummy_desired_state)

        time.sleep(5)

        current_state = statelib.show_only((DUMMY_INTERFACE,))
        assert len(current_state[Interface.KEY]) == 1
