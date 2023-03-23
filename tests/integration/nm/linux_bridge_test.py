# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest
from contextlib import contextmanager

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
from ..testlib.env import is_k8s
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


@pytest.fixture
def external_managed_bridge_with_unmanaged_ports():
    exec_cmd(f"ip link add {BRIDGE0} type bridge".split(), check=True)
    try:
        with dummy_as_port(BRIDGE0, DUMMY0), dummy_as_port(BRIDGE0, DUMMY1):
            yield
    finally:
        exec_cmd(f"ip link delete {BRIDGE0}".split())
        exec_cmd(f"nmcli c del {BRIDGE0}".split())


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


@contextmanager
def dummy_as_port(controller, dummy_iface):
    exec_cmd(("ip", "link", "add", dummy_iface, "type", "dummy"), check=True)
    try:
        exec_cmd(("ip", "link", "set", dummy_iface, "up"), check=True)
        exec_cmd(
            ("nmcli", "dev", "set", dummy_iface, "managed", "no"), check=True
        )
        exec_cmd(
            ("ip", "link", "set", dummy_iface, "master", controller),
            check=True,
        )
        yield
    finally:
        exec_cmd(("ip", "link", "delete", dummy_iface))
        exec_cmd(("nmcli", "c", "del", dummy_iface))


def test_linux_manage_bridge_keeps_unmanaged_port(
    external_managed_bridge_with_unmanaged_ports,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE0,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.LINUX_BRIDGE,
            },
            {
                Interface.NAME: DUMMY1,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.DUMMY,
            },
        ]
    }
    libnmstate.apply(desired_state)

    current_state = show_only((BRIDGE0,))
    bridge_state = current_state[Interface.KEY][0][LB.CONFIG_SUBTREE]
    port_names = [port[LB.Port.NAME] for port in bridge_state[LB.PORT_SUBTREE]]

    assert DUMMY0 in port_names
    assert DUMMY1 in port_names


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


def test_partially_consume_linux_bridge_port(
    external_managed_bridge_with_unmanaged_ports,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE0,
                Interface.STATE: InterfaceState.UP,
            },
            {
                Interface.NAME: DUMMY0,
                Interface.STATE: InterfaceState.UP,
            },
        ]
    }
    libnmstate.apply(desired_state)

    current_state = show_only((BRIDGE0,))
    bridge_state = current_state[Interface.KEY][0][LB.CONFIG_SUBTREE]
    port_names = [port[LB.Port.NAME] for port in bridge_state[LB.PORT_SUBTREE]]
    assert port_names == [DUMMY0, DUMMY1]
    assert (
        "connected"
        in exec_cmd(
            f"nmcli -g GENERAL.STATE d show {BRIDGE0}".split(), check=True
        )[1]
    )
    assert (
        "connected"
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


@pytest.mark.tier1
@pytest.mark.skipif(
    is_k8s(),
    reason="K8S CI is using ifcfg which does not support this use case. "
    "Meanwhile k8s does not have this requirement",
)
def test_linux_bridge_store_stp_setting_even_disabled(
    eth1_up,
):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.PORT_SUBTREE: [
                {
                    LB.Port.NAME: "eth1",
                }
            ],
            LB.OPTIONS_SUBTREE: {
                LB.STP_SUBTREE: {
                    LB.STP.ENABLED: False,
                    LB.STP.FORWARD_DELAY: 16,
                    LB.STP.HELLO_TIME: 2,
                    LB.STP.MAX_AGE: 20,
                    LB.STP.PRIORITY: 20480,
                }
            },
        },
    ) as state:
        assertlib.assert_state_match(state)
        assert (
            exec_cmd(
                f"nmcli -g bridge.stp c show {BRIDGE0}".split(),
            )[1].strip()
            == "no"
        )
        assert (
            exec_cmd(
                f"nmcli -g bridge.forward-delay c show {BRIDGE0}".split(),
            )[1].strip()
            == "16"
        )
        assert (
            exec_cmd(
                f"nmcli -g bridge.hello-time c show {BRIDGE0}".split(),
            )[1].strip()
            == "2"
        )
        assert (
            exec_cmd(
                f"nmcli -g bridge.max-age c show {BRIDGE0}".split(),
            )[1].strip()
            == "20"
        )
        assert (
            exec_cmd(
                f"nmcli -g bridge.priority c show {BRIDGE0}".split(),
            )[1].strip()
            == "20480"
        )


@pytest.fixture
def unmangaed_dummy1_dummy2():
    exec_cmd("ip link add dummy1 type dummy".split(), check=True)
    exec_cmd("ip link add dummy2 type dummy".split(), check=True)
    exec_cmd("ip link set dummy1 up".split(), check=True)
    exec_cmd("ip link set dummy2 up".split(), check=True)
    exec_cmd("nmcli dev set dummy1 managed false".split(), check=True)
    exec_cmd("nmcli dev set dummy2 managed false".split(), check=True)
    yield
    exec_cmd("ip link del dummy1".split(), check=False)
    exec_cmd("ip link del dummy2".split(), check=False)


def test_auto_manage_linux_ignored_ports(unmangaed_dummy1_dummy2):
    bridge_subtree_state = {
        LB.PORT_SUBTREE: [
            {LB.Port.NAME: "dummy1"},
            {LB.Port.NAME: "dummy2"},
        ],
        LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}},
    }
    with linux_bridge(
        BRIDGE0, bridge_subtree_state=bridge_subtree_state
    ) as state:
        assertlib.assert_state_match(state)


@pytest.fixture
def br0_down(eth1_up):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.PORT_SUBTREE: [
                {
                    LB.Port.NAME: "eth1",
                }
            ],
            LB.OPTIONS_SUBTREE: {
                LB.STP_SUBTREE: {
                    LB.STP.ENABLED: False,
                }
            },
        },
    ) as state:
        exec_cmd(f"nmcli c down {BRIDGE0}".split(), check=True)
        yield state


def test_activate_nmcli_down_linux_bridge(br0_down):
    br0_up_state = br0_down
    libnmstate.apply(br0_up_state)
    assertlib.assert_state_match(br0_up_state)


def test_create_down_linux_bridge(br0_down):
    state = br0_down
    state[Interface.KEY][0][Interface.STATE] = InterfaceState.DOWN
    libnmstate.apply(state)
    assertlib.assert_absent(BRIDGE0)
    exec_cmd(f"nmcli c show {BRIDGE0}".split(), check=True)
    exec_cmd("nmcli c show eth1".split(), check=True)
