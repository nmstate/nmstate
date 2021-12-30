#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from .testlib import assertlib
from .testlib import statelib


MAC1 = "00:11:22:33:44:55"
MAC2 = "00:11:22:33:44:66"
MAC3 = "00:11:22:33:44:FF"
MAC_MIX_CASE = "00:11:22:33:44:Ff"

VF0_CONF = {
    Ethernet.SRIOV.VFS.ID: 0,
    Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
    Ethernet.SRIOV.VFS.MAC_ADDRESS: MAC1,
    Ethernet.SRIOV.VFS.TRUST: False,
}

VF1_CONF = {
    Ethernet.SRIOV.VFS.ID: 1,
    Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
    Ethernet.SRIOV.VFS.MAC_ADDRESS: MAC2,
    Ethernet.SRIOV.VFS.TRUST: False,
}


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


@pytest.fixture
def sriov_iface_vf(disable_sriov):
    pf_name = _test_nic_name()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: pf_name,
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {
                        Ethernet.SRIOV.TOTAL_VFS: 2,
                        Ethernet.SRIOV.VFS_SUBTREE: [VF0_CONF, VF1_CONF],
                    }
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    yield desired_state


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_with_no_vfs_config(sriov_interface):
    assertlib.assert_state_match(sriov_interface)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_increase_vfs(sriov_interface):
    desired_state = sriov_interface
    eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 5
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_decrease_vfs(sriov_interface):
    desired_state = sriov_interface
    eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 1
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = [VF0_CONF]
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_create_vf_config(sriov_iface_vf):
    assertlib.assert_state_match(sriov_iface_vf)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_edit_vf_config(sriov_iface_vf):
    desired_state = sriov_iface_vf
    eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    vf0 = eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE][0]
    vf0[Ethernet.SRIOV.VFS.TRUST] = True
    vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = MAC3
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
@pytest.mark.xfail(
    raises=libnmstate.error.NmstateVerificationError,
    reason="https://github.com/nmstate/nmstate/issues/1454",
    strict=True,
)
def test_sriov_remove_vf_config(sriov_iface_vf):
    desired_state = sriov_iface_vf
    eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = []
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_vf_mac_mixed_case(sriov_iface_vf):
    desired_state = sriov_iface_vf
    eth_config = desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    vf0 = eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE][0]
    vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = MAC_MIX_CASE
    libnmstate.apply(desired_state)

    vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = MAC_MIX_CASE.upper()
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_wait_sriov_vf_been_created():
    pf_name = _test_nic_name()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: pf_name,
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
                },
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
        current_state = statelib.show_only((f"{pf_name}v0", f"{pf_name}v1"))
        assert len(current_state[Interface.KEY]) == 2

    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_wait_sriov_vf_been_deleted_when_total_vfs_decrease():
    pf_name = _test_nic_name()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: pf_name,
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
                },
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
        current_state = statelib.show_only((f"{pf_name}v0", f"{pf_name}v1"))
        assert len(current_state[Interface.KEY]) == 2

        desired_state[Interface.KEY][0][Ethernet.CONFIG_SUBTREE][
            Ethernet.SRIOV_SUBTREE
        ][Ethernet.SRIOV.TOTAL_VFS] = 1
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
        current_state = statelib.show_only((f"{pf_name}v0", f"{pf_name}v1"))
        assert len(current_state[Interface.KEY]) == 1

    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for SR-IOV test",
)
def test_sriov_vf_vlan_id_and_qos():
    pf_name = _test_nic_name()
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: pf_name,
                Ethernet.CONFIG_SUBTREE: {
                    Ethernet.SRIOV_SUBTREE: {
                        Ethernet.SRIOV.TOTAL_VFS: 2,
                        Ethernet.SRIOV.VFS_SUBTREE: [
                            {
                                Ethernet.SRIOV.VFS.ID: 0,
                                Ethernet.SRIOV.VFS.VLAN_ID: 100,
                                Ethernet.SRIOV.VFS.QOS: 5,
                            },
                            {
                                Ethernet.SRIOV.VFS.ID: 1,
                                Ethernet.SRIOV.VFS.VLAN_ID: 102,
                                Ethernet.SRIOV.VFS.QOS: 6,
                            },
                        ],
                    }
                },
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)
