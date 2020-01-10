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

from contextlib import contextmanager

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.error import NmstateLibnmError

from .testlib import assertlib
from .testlib import cmd as libcmd
from .testlib.ovslib import Bridge
from .testlib.vlan import vlan_interface


BRIDGE1 = "br1"
PORT1 = "ovs1"
VLAN_IFNAME = "eth101"

DNF_REMOVE_NM_OVS_CMD = ("dnf", "remove", "-y", "-q", "NetworkManager-ovs")
DNF_INSTALL_NM_OVS_CMD = ("dnf", "install", "-y", "-q", "NetworkManager-ovs")
SYSTEMCTL_RESTART_NM_CMD = ("systemctl", "restart", "NetworkManager")


@pytest.mark.xfail(
    raises=(NmstateLibnmError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_create_and_remove_ovs_bridge_with_min_desired_state():
    with Bridge(BRIDGE1).create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.xfail(
    raises=(NmstateLibnmError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_create_and_remove_ovs_bridge_options_specified():
    bridge = Bridge(BRIDGE1)
    bridge.set_options(
        {
            OVSBridge.Options.FAIL_MODE: "",
            OVSBridge.Options.MCAST_SNOOPING_ENABLED: False,
            OVSBridge.Options.RSTP: False,
            OVSBridge.Options.STP: True,
        }
    )

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.xfail(
    raises=(NmstateLibnmError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_create_and_remove_ovs_bridge_with_a_system_port(port0_up):
    bridge = Bridge(BRIDGE1)
    port0_name = port0_up[Interface.KEY][0][Interface.NAME]
    bridge.add_system_port(port0_name)

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.xfail(
    raises=(NmstateLibnmError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_create_and_remove_ovs_bridge_with_internal_port_static_ip_and_mac():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        PORT1,
        mac="02:ff:ff:ff:ff:01",
        ipv4_state={
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.0.2.1",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        },
    )

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)


def test_vlan_as_ovs_bridge_slave(vlan_on_eth1):
    bridge = Bridge(BRIDGE1)
    bridge.add_system_port(vlan_on_eth1)
    with bridge.create() as state:
        assertlib.assert_state_match(state)


def test_nm_ovs_plugin_missing():
    with disable_nm_ovs_plugin():
        with pytest.raises(NmstateLibnmError):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: BRIDGE1,
                            Interface.TYPE: InterfaceType.OVS_BRIDGE,
                            Interface.STATE: InterfaceState.UP,
                        }
                    ]
                }
            )


@contextmanager
def disable_nm_ovs_plugin():
    libcmd.exec_cmd(DNF_REMOVE_NM_OVS_CMD)
    libcmd.exec_cmd(SYSTEMCTL_RESTART_NM_CMD)
    try:
        yield
    finally:
        libcmd.exec_cmd(DNF_INSTALL_NM_OVS_CMD)
        libcmd.exec_cmd(SYSTEMCTL_RESTART_NM_CMD)


@pytest.fixture
def vlan_on_eth1(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        yield VLAN_IFNAME
