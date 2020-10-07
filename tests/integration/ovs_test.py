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

import time

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstateValueError

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import nmlib
from .testlib import statelib
from .testlib.nmplugin import disable_nm_plugin
from .testlib.ovslib import Bridge
from .testlib.vlan import vlan_interface


BOND1 = "bond1"
BRIDGE1 = "br1"
PORT1 = "ovs1"
VLAN_IFNAME = "eth101"


@pytest.fixture
def bridge_with_ports(port0_up):
    system_port0_name = port0_up[Interface.KEY][0][Interface.NAME]

    bridge = Bridge(BRIDGE1)
    bridge.add_system_port(system_port0_name)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
    with bridge.create():
        yield bridge


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

    state = statelib.show_only((port0_name,))
    assert state
    assert state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP


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


@pytest.mark.xfail(
    raises=NmstateValueError,
    reason="https://nmstate.atlassian.net/browse/NMSTATE-286",
    strict=True,
)
def test_create_and_remove_ovs_bridge_with_internal_port_same_name():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        BRIDGE1, ipv4_state={InterfaceIPv4.ENABLED: False}
    )

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


def test_vlan_as_ovs_bridge_slave(vlan_on_eth1):
    bridge = Bridge(BRIDGE1)
    bridge.add_system_port(vlan_on_eth1)
    with bridge.create() as state:
        assertlib.assert_state_match(state)


@pytest.mark.xfail(
    raises=(NmstateLibnmError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_ovs_interface_with_max_length_name():
    bridge = Bridge(BRIDGE1)
    ovs_interface_name = "ovs123456789012"
    bridge.add_internal_port(ovs_interface_name)

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(ovs_interface_name)


def test_nm_ovs_plugin_missing():
    with disable_nm_plugin("ovs"):
        with pytest.raises(NmstateDependencyError):
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


@pytest.mark.xfail(
    raises=NmstateLibnmError, reason="https://bugzilla.redhat.com/1724901"
)
def test_ovs_remove_port(bridge_with_ports):
    for port_name in bridge_with_ports.ports_names:
        nm_port_profile_name = nmlib.get_ovs_port_by_slave(port_name)
        assert nmlib.list_profiles_by_iface_name(nm_port_profile_name)
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: port_name,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )
        assert not nmlib.list_profiles_by_iface_name(nm_port_profile_name)


@pytest.fixture
def vlan_on_eth1(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        yield VLAN_IFNAME


def test_change_ovs_interface_mac():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})

    with bridge.create() as state:
        desired_state = {
            Interface.KEY: [
                {Interface.NAME: PORT1, Interface.MAC: "32:e4:ff:ff:ff:ff"}
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)


class TestOvsLinkAggregation:
    def test_create_and_remove_lag(self, port0_up, port1_up):
        port0_name = port0_up[Interface.KEY][0][Interface.NAME]
        port1_name = port1_up[Interface.KEY][0][Interface.NAME]

        bridge = Bridge(BRIDGE1)
        bridge.add_link_aggregation_port(BOND1, (port0_name, port1_name))

        with bridge.create() as state:
            assertlib.assert_state_match(state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BOND1)


def test_ovs_vlan_access_tag():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
    bridge.set_port_option(
        PORT1,
        {
            OVSBridge.Port.NAME: PORT1,
            OVSBridge.Port.VLAN_SUBTREE: {
                OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.ACCESS,
                OVSBridge.Port.Vlan.TAG: 2,
            },
        },
    )
    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)


@pytest.fixture
def ovs_bridge_with_internal_interface_and_identical_names():
    device_name = "obridge0"

    cmdlib.exec_cmd(
        [
            "nmcli",
            "connection",
            "add",
            "type",
            "ovs-bridge",
            "conn.interface",
            device_name,
        ],
        check=True,
    )
    cmdlib.exec_cmd(
        [
            "nmcli",
            "connection",
            "add",
            "type",
            "ovs-port",
            "conn.interface",
            device_name,
            "master",
            device_name,
        ],
        check=True,
    )
    cmdlib.exec_cmd(
        [
            "nmcli",
            "connection",
            "add",
            "type",
            "ovs-interface",
            "slave-type",
            "ovs-port",
            "conn.interface",
            device_name,
            "master",
            device_name,
        ],
        check=True,
    )

    try:
        yield device_name
    finally:
        _, con_names, _ = cmdlib.exec_cmd(
            ["nmcli", "-f", "NAME", "connection"], check=True,
        )
        con_to_delete = [
            con_name.strip()
            for con_name in con_names.splitlines()
            if device_name in con_name
        ]
        cmdlib.exec_cmd(
            ["nmcli", "connection", "delete"] + con_to_delete, check=True,
        )
        # Wait for command to take affect.
        time.sleep(1)

        assertlib.assert_absent(device_name)


def test_ovs_report_with_identical_inteface_names(
    ovs_bridge_with_internal_interface_and_identical_names,
):
    name = ovs_bridge_with_internal_interface_and_identical_names
    state = statelib.show_only((name,))

    assert state
    assert len(state[Interface.KEY]) == 2
