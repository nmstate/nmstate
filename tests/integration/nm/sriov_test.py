# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2021 Red Hat, Inc.
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

import os

import pytest

import libnmstate
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from ..testlib import cmdlib


def _test_nic_name():
    return os.environ.get("TEST_REAL_NIC")


@pytest.fixture
def disable_sriov():
    pf_name = _test_nic_name()
    iface_info = {
        Interface.NAME: pf_name,
        Interface.STATE: InterfaceState.UP,
        Ethernet.CONFIG_SUBTREE: {
            Ethernet.SRIOV_SUBTREE: {
                Ethernet.SRIOV.TOTAL_VFS: 0,
                Ethernet.SRIOV.VFS_SUBTREE: [],
            }
        },
    }
    desired_state = {Interface.KEY: [iface_info]}
    libnmstate.apply(desired_state)
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.fixture
def sriov_interface(disable_sriov):
    pf_name = _test_nic_name()
    iface_info = {
        Interface.NAME: pf_name,
        Interface.STATE: InterfaceState.UP,
        Ethernet.CONFIG_SUBTREE: {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2},
        },
    }
    desired_state = {Interface.KEY: [iface_info]}
    libnmstate.apply(desired_state)
    yield desired_state


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_create_new_vfs_does_not_generate_a_profile(sriov_interface):
    desired_state = sriov_interface
    pf_name = sriov_interface[Interface.KEY][0][Interface.NAME]
    eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 5
    libnmstate.apply(desired_state)
    _, out, _ = cmdlib.exec_cmd("nmcli c".split(), check=True)

    assert f"{pf_name}v0" not in out
    assert f"{pf_name}v1" not in out
