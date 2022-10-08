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
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState

from ..testlib import cmdlib
from ..testlib import statelib


IPV4_ADDRESS1 = "192.0.2.251"


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


@pytest.fixture
def sriov_created_by_other_tool(disable_sriov):
    pf_name = _test_nic_name()
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
    cmdlib.exec_cmd(f"ip link set {pf_name} up".split(), check=True)
    with open(f"/sys/class/net/{pf_name}/device/sriov_numvfs", "w") as fd:
        fd.write("2\n")
    yield


@pytest.mark.tier1
@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_do_not_changed_sriov_if_not_mentioned(sriov_created_by_other_tool):
    pf_name = _test_nic_name()
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: pf_name,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                }
            ]
        }
    )
    current_state = statelib.show_only((f"{pf_name}",))
    assert (
        current_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE][
            Ethernet.SRIOV_SUBTREE
        ][Ethernet.SRIOV.TOTAL_VFS]
        == 2
    )
    assert not cmdlib.exec_cmd(f"nmcli -f sriov  c show {pf_name}".split())[
        1
    ].strip()
