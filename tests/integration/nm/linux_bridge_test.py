#
# Copyright (c) 2018-2022 Red Hat, Inc.
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

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import VLAN

from ..testlib import assertlib
from ..testlib.bondlib import bond_interface
from ..testlib.bridgelib import linux_bridge
from ..testlib.cmdlib import exec_cmd
from ..testlib.dummy import nm_unmanaged_dummy
from ..testlib.env import nm_minor_version
from ..testlib.statelib import show_only


BRIDGE0 = "brtest0"
DUMMY0 = "dummy0"
DUMMY1 = "dummy1"

VETH0 = "vethtest0"


@pytest.fixture
def nm_unmanaged_dummy1():
    with nm_unmanaged_dummy(DUMMY1):
        yield


@pytest.mark.tier1
def test_bridge_consume_unmanaged_interface_as_port(nm_unmanaged_dummy1):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}}
        },
    ) as desired_state:
        bridge_iface_state = desired_state[Interface.KEY][0]
        bridge_iface_state[LB.CONFIG_SUBTREE] = {
            LB.PORT_SUBTREE: [{LB.Port.NAME: DUMMY1}],
        }
        # To reproduce bug https://bugzilla.redhat.com/1816517
        # explitly define dummy1 as IPv4/IPv6 disabled is required.
        # explitly define dummy1 in desire is required for unmanaged interface.
        desired_state[Interface.KEY].append(
            {
                Interface.NAME: DUMMY1,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        )
        libnmstate.apply(desired_state)


@pytest.mark.tier1
def test_add_new_port_to_bridge_with_unmanged_port(
    nm_unmanaged_dummy1, eth1_up, eth2_up
):
    bridge_subtree_state = {
        LB.PORT_SUBTREE: [{LB.Port.NAME: "eth1"}],
        LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}},
    }

    with linux_bridge(BRIDGE0, bridge_subtree_state=bridge_subtree_state):
        exec_cmd(f"ip link set {DUMMY1} master {BRIDGE0}".split(), check=True)
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: BRIDGE0,
                        LB.CONFIG_SUBTREE: {
                            LB.PORT_SUBTREE: [
                                {LB.Port.NAME: "eth1"},
                                {LB.Port.NAME: "eth2"},
                            ]
                        },
                    }
                ]
            }
        )

        # dummy1 should still be the bridge port
        output = exec_cmd(f"npc iface {DUMMY1}".split(), check=True)[1]
        assert f"controller: {BRIDGE0}" in output


@pytest.fixture
def bond0_with_multiple_profile(eth1_up, eth2_up):
    bond_ifname = "testbond0"
    new_connection_name = f"{bond_ifname}_dup"
    with bond_interface(bond_ifname, ["eth1", "eth2"]):
        exec_cmd(
            f"nmcli c add connection.id {new_connection_name} type bond "
            f"ifname {bond_ifname} ipv4.method disabled ipv6.method disabled "
            "connection.autoconnect false".split(),
            check=True,
        )
        yield bond_ifname
    exec_cmd(f"nmcli c del {new_connection_name}".split(), check=False)


@pytest.mark.tier1
def test_linux_bridge_over_vlan_of_bond_with_multiple_profile(
    bond0_with_multiple_profile,
):
    bond_ifname = bond0_with_multiple_profile
    vlan_id = 400
    vlan_ifname = f"{bond_ifname}.{vlan_id}"
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}},
            LB.PORT_SUBTREE: [{LB.Port.NAME: vlan_ifname}],
        },
        create=False,
    ) as state:
        state[Interface.KEY].append(
            {
                Interface.NAME: vlan_ifname,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.VLAN,
                VLAN.CONFIG_SUBTREE: {
                    VLAN.ID: vlan_id,
                    VLAN.BASE_IFACE: bond_ifname,
                },
            }
        )

        libnmstate.apply(state)
        assertlib.assert_state_match(state)


@pytest.fixture
def unmanged_veth0():
    veth_iface = VETH0
    exec_cmd(
        f"ip link add {veth_iface} type veth peer {veth_iface}.ep".split(),
        check=False,
    )
    exec_cmd(f"ip link set {veth_iface}.ep up".split(), check=True)
    yield
    exec_cmd(f"ip link del {veth_iface}".split())
    exec_cmd(f"nmcli c del {veth_iface}".split())


@pytest.fixture
def bridge_with_unmanaged_port(eth1_up, unmanged_veth0):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}},
            LB.PORT_SUBTREE: [{LB.Port.NAME: "eth1"}],
        },
    ):
        exec_cmd(f"ip link set {VETH0} master {BRIDGE0}".split(), check=True)
        yield


@pytest.mark.tier1
@pytest.mark.xfail(
    nm_minor_version() < 39,
    raises=AssertionError,
    reason="https://bugzilla.redhat.com/2076131",
    strict=True,
)
def test_linux_bridge_does_not_lose_unmanaged_port_on_rollback(
    bridge_with_unmanaged_port,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE0,
                    Interface.STATE: InterfaceState.UP,
                    Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                    Interface.MTU: 1450,
                },
            ]
        },
        commit=False,
    )
    libnmstate.rollback()
    current_state = show_only((BRIDGE0,))
    bridge_state = current_state[Interface.KEY][0][LB.CONFIG_SUBTREE]
    port_names = [port[LB.Port.NAME] for port in bridge_state[LB.PORT_SUBTREE]]
    assert "eth1" in port_names
    assert VETH0 in port_names


def test_ignore_interface_mentioned_in_port_list(
    external_managed_bridge_with_unmanaged_ports, eth1_up
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE0,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                LB.CONFIG_SUBTREE: {
                    LB.PORT_SUBTREE: [
                        {LB.Port.NAME: DUMMY0},
                        {LB.Port.NAME: DUMMY1},
                        {LB.Port.NAME: "eth1"},
                    ],
                },
            },
        ]
    }
    libnmstate.apply(desired_state)
    assert (
        "unmanaged"
        in exec_cmd(
            f"nmcli -g GENERAL.STATE d show {DUMMY0}".split(), check=True
        )[1]
    )
    assert (
        "unmanaged"
        in exec_cmd(
            f"nmcli -g GENERAL.STATE d show {DUMMY1}".split(), check=True
        )[1]
    )
