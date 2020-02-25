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

from subprocess import CalledProcessError

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateValueError

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import statelib
from .testlib.nmplugin import disable_nm_plugin
from .testlib.ovslib import Bridge
from .testlib.servicelib import disable_service
from .testlib.ovslib import get_proxy_port_profile_name_of_ovs_interface
from .testlib.ovslib import get_nm_active_profiles
from .testlib.vlan import vlan_interface


BOND1 = "bond1"
BRIDGE1 = "br1"
PORT1 = "ovs1"
VLAN_IFNAME = "eth101"

MAC1 = "02:FF:FF:FF:FF:01"


@pytest.fixture
def bridge_with_ports(port0_up):
    system_port0_name = port0_up[Interface.KEY][0][Interface.NAME]

    bridge = Bridge(BRIDGE1)
    bridge.add_system_port(system_port0_name)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
    with bridge.create():
        yield bridge


@pytest.mark.tier1
def test_create_and_remove_ovs_bridge_with_min_desired_state():
    with Bridge(BRIDGE1).create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


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


@pytest.mark.tier1
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


@pytest.mark.tier1
def test_create_and_remove_ovs_bridge_with_internal_port_static_ip_and_mac():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        PORT1,
        mac=MAC1,
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


@pytest.mark.tier1
def test_vlan_as_ovs_bridge_slave(vlan_on_eth1):
    bridge = Bridge(BRIDGE1)
    bridge.add_system_port(vlan_on_eth1)
    with bridge.create() as state:
        assertlib.assert_state_match(state)


@pytest.mark.tier1
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


def test_ovs_service_missing():
    with disable_service("openvswitch"):
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

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.mark.tier1
def test_ovs_remove_port(bridge_with_ports):
    for port_name in bridge_with_ports.ports_names:
        active_profiles = get_nm_active_profiles()
        assert port_name in active_profiles
        proxy_port_profile = get_proxy_port_profile_name_of_ovs_interface(
            port_name
        )
        assert proxy_port_profile
        assert proxy_port_profile in active_profiles
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

        with pytest.raises(CalledProcessError):
            cmdlib.exec_cmd(
                f"nmcli connection show {proxy_port_profile}".split(" "),
                check=True,
            )


@pytest.fixture
def vlan_on_eth1(eth1_up):
    with vlan_interface(
        VLAN_IFNAME, 101, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        yield VLAN_IFNAME


@pytest.mark.tier1
def test_change_ovs_interface_mac():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})

    with bridge.create() as state:
        desired_state = {
            Interface.KEY: [{Interface.NAME: PORT1, Interface.MAC: MAC1}]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)


class TestOvsLinkAggregation:
    @pytest.mark.tier1
    def test_create_and_remove_lag(self, port0_up, port1_up):
        port0_name = port0_up[Interface.KEY][0][Interface.NAME]
        port1_name = port1_up[Interface.KEY][0][Interface.NAME]

        bridge = Bridge(BRIDGE1)
        bridge.add_link_aggregation_port(BOND1, (port0_name, port1_name))

        with bridge.create() as state:
            assertlib.assert_state_match(state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BOND1)


@pytest.mark.tier1
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


def test_add_invalid_slave_ip_config(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.ENABLED] = True
    desired_state[Interface.KEY][0][Interface.IPV4][InterfaceIP.DHCP] = True
    with pytest.raises(NmstateValueError):
        bridge = Bridge(name=BRIDGE1)
        bridge.add_system_port("eth1")
        with bridge.create() as state:
            desired_state[Interface.KEY].append(state[Interface.KEY][0])
            libnmstate.apply(desired_state)
