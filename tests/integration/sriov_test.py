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
from libnmstate.error import NmstateNotSupportedError
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface

from .testlib import assertlib


SRIOV_CONFIG = {Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}}


pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true", reason="CI devices do not support SR-IOV",
)


@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_sriov_zero_vfs(sriov_interface):
    assertlib.assert_state(sriov_interface)


@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_sriov_increase_vfs(sriov_interface):
    eth_config = sriov_interface[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 5
    libnmstate.apply(sriov_interface)
    assertlib.assert_state(sriov_interface)


@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_sriov_decrease_vfs(sriov_interface):
    eth_config = sriov_interface[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.TOTAL_VFS] = 0
    libnmstate.apply(sriov_interface)
    assertlib.assert_state(sriov_interface)


@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_sriov_create_vf_config(sriov_interface):
    eth_config = sriov_interface[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = [
        {
            Ethernet.SRIOV.VFS.ID: 0,
            Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
            Ethernet.SRIOV.VFS.MAC_ADDRESS: "00:11:22:33:44:55",
            Ethernet.SRIOV.VFS.TRUST: False,
        }
    ]
    libnmstate.apply(sriov_interface)
    assertlib.assert_state(sriov_interface)


@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_sriov_edit_vf_config(sriov_iface_vf):
    eth_config = sriov_iface_vf[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    vf0 = eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE][0]
    vf0[Ethernet.SRIOV.VFS.TRUST] = True
    vf0[Ethernet.SRIOV.VFS.MAC_ADDRESS] = "55:44:33:22:11:00"
    libnmstate.apply(sriov_interface)
    assertlib.assert_state(sriov_interface)


@pytest.mark.xfail(
    raises=NmstateNotSupportedError,
    reason="The device does not support SR-IOV.",
)
def test_sriov_remove_vf_config(sriov_iface_vf):
    eth_config = sriov_iface_vf[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = []
    libnmstate.apply(sriov_interface)
    assertlib.assert_state(sriov_interface)


@pytest.fixture
def sriov_interface(eth1_up):
    eth1_up[Interface.KEY][0][Ethernet.CONFIG_SUBTREE] = SRIOV_CONFIG
    libnmstate.apply(eth1_up)
    yield eth1_up


@pytest.fixture
def sriov_iface_vf(eth1_up):
    eth1_up[Interface.KEY][0][Ethernet.CONFIG_SUBTREE] = SRIOV_CONFIG
    eth_config = eth1_up[Interface.KEY][0][Ethernet.CONFIG_SUBTREE]
    eth_config[Ethernet.SRIOV_SUBTREE][Ethernet.SRIOV.VFS_SUBTREE] = [
        {
            Ethernet.SRIOV.VFS.ID: 0,
            Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
            Ethernet.SRIOV.VFS.MAC_ADDRESS: "00:11:22:33:44:55",
            Ethernet.SRIOV.VFS.TRUST: False,
        }
    ]
    libnmstate.apply(eth1_up)
    yield eth1_up
