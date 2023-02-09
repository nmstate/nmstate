#
# Copyright (c) 2019-2021 Red Hat, Inc.
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
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import VLAN

from ..testlib import assertlib
from ..testlib import cmdlib
from ..testlib import statelib
from ..testlib.ovslib import Bridge
from ..testlib.retry import retry_till_true_or_timeout


BRIDGE0 = "brtest0"
BRIDGE1 = "brtest1"
IFACE0 = "ovstest0"
OVSDB_EXT_IDS_CONF1 = {"foo": "abc", "bak": 1}
OVSDB_EXT_IDS_CONF1_STR = {"foo": "abc", "bak": "1"}
OVSDB_EXT_IDS_CONF2 = {"bak": 2}
OVSDB_EXT_IDS_CONF2_STR = {"bak": "2"}
OVS_DUP_NAME = "br-ex"
ETH1 = "eth1"
VERIFY_RETRY_TMO = 5


@pytest.fixture
def bridge_with_ports(eth1_up):
    bridge = Bridge(BRIDGE0)
    bridge.add_system_port(ETH1)
    bridge.add_internal_port(IFACE0, ipv4_state={InterfaceIPv4.ENABLED: False})
    with bridge.create():
        yield bridge


@pytest.fixture
def bridge_port_types():
    yield {
        ETH1: InterfaceType.ETHERNET,
        IFACE0: InterfaceType.OVS_INTERFACE,
    }


@pytest.fixture
def ovs_unmanaged_bridge():
    cmdlib.exec_cmd(f"ovs-vsctl add-br {BRIDGE0}".split())
    yield
    cmdlib.exec_cmd(f"ovs-vsctl del-br {BRIDGE0}".split())


@pytest.mark.tier1
def test_do_not_show_unmanaged_ovs_bridge(ovs_unmanaged_bridge):
    # The output should only contains the OVS internal interface
    ovs_internal_iface = statelib.show_only((BRIDGE0,))[Interface.KEY][0]
    assert ovs_internal_iface[Interface.TYPE] == InterfaceType.OVS_INTERFACE


@pytest.fixture
def nmcli_created_ovs_bridge_with_same_name_iface():
    cmdlib.exec_cmd(
        "nmcli c add type ovs-bridge connection.id "
        f"{BRIDGE0} ifname {BRIDGE0}".split()
    )

    cmdlib.exec_cmd(
        "nmcli c add type ovs-port connection.id "
        f"{IFACE0} ifname {IFACE0} "
        f"connection.master {BRIDGE0} connection.slave-type ovs-bridge".split()
    )

    cmdlib.exec_cmd(
        "nmcli c add type ovs-interface connection.id "
        f"{IFACE0} ifname {IFACE0} "
        f"ipv4.method disabled ipv6.method disabled "
        f"connection.master {IFACE0} connection.slave-type ovs-port".split()
    )

    yield
    cmdlib.exec_cmd(f"ovs-vsctl del-br {BRIDGE0} {IFACE0} ".split())


@pytest.mark.tier1
def test_create_vlan_over_existing_ovs_iface_with_use_same_name_as_bridge(
    nmcli_created_ovs_bridge_with_same_name_iface,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "vlan101",
                Interface.TYPE: InterfaceType.VLAN,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: IFACE0},
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state, verify_change=False)


class _OvsProfileStillExists(Exception):
    pass


@pytest.mark.tier1
def test_remove_ovs_internal_iface_got_port_profile_removed(
    bridge_with_ports, bridge_port_types
):
    for ovs_iface_name in bridge_with_ports.ports_names:
        active_profile_names, active_profile_uuids = _get_nm_active_profiles()
        assert ovs_iface_name in active_profile_names
        if bridge_port_types[ovs_iface_name] == InterfaceType.OVS_INTERFACE:
            ovs_port_profile_uuid = (
                _get_ovs_port_profile_uuid_of_ovs_interface(ovs_iface_name)
            )
        else:
            ovs_port_profile_uuid = _get_parent_uuid_of_interface(
                ovs_iface_name
            )
        assert ovs_port_profile_uuid
        assert ovs_port_profile_uuid in active_profile_uuids
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ovs_iface_name,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )

        rc, output, _ = cmdlib.exec_cmd(
            f"nmcli c show {ovs_port_profile_uuid}".split(" "),
        )
        if rc == 0:
            raise _OvsProfileStillExists(
                f"{ovs_port_profile_uuid} still exists: {output}"
            )


@pytest.mark.tier1
def test_remove_ovs_bridge_ignored_port_keeps_it(bridge_with_ports):
    d_state = bridge_with_ports.state
    ovs_config = d_state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE]
    ovs_config[OVSBridge.PORT_SUBTREE] = [{OVSBridge.Port.NAME: IFACE0}]
    d_state[Interface.KEY].append(
        {Interface.NAME: ETH1, Interface.STATE: InterfaceState.IGNORE}
    )

    libnmstate.apply(d_state)

    current_state = statelib.show_only((ETH1, BRIDGE0))
    current_ovs = current_state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE]
    ovs_port_names = [
        ovs_port[OVSBridge.Port.NAME]
        for ovs_port in current_ovs[OVSBridge.PORT_SUBTREE]
    ]
    assert (
        current_state[Interface.KEY][0][Interface.STATE] == InterfaceState.UP
    )
    assert ETH1 in ovs_port_names


def _get_nm_active_profiles():
    all_profile_names_output = cmdlib.exec_cmd(
        "nmcli -g NAME connection show --active".split(" "), check=True
    )[1]
    all_profile_uuids_output = cmdlib.exec_cmd(
        "nmcli -g UUID connection show --active".split(" "), check=True
    )[1]
    return (
        all_profile_names_output.split("\n"),
        all_profile_uuids_output.split("\n"),
    )


def _get_ovs_port_profile_uuid_of_ovs_interface(iface_name):
    ovs_iface_uuid = _get_uuid_of_ovs_interface(iface_name)
    ovs_port_uuid = _get_parent_uuid_of_interface(ovs_iface_uuid)
    cmdlib.exec_cmd(
        f"nmcli -g connection.id connection show {ovs_port_uuid}".split(" "),
        check=True,
    )
    return ovs_port_uuid


def _get_uuid_of_ovs_interface(iface_name):
    conns = cmdlib.exec_cmd(
        "nmcli -g name,uuid,type connection show".split(" "),
        check=True,
    )[1].split("\n")
    ovs_iface_conns = [
        x for x in conns if "ovs-interface" in x and iface_name in x
    ]
    if len(ovs_iface_conns) == 0:
        return ""
    else:
        return ovs_iface_conns[0].split(":")[1]


def _get_parent_uuid_of_interface(iface_name):
    return cmdlib.exec_cmd(
        f"nmcli -g connection.master connection show {iface_name}".split(" "),
        check=True,
    )[1].strip()


def _nmcli_ovs_bridge_with_ipv4_dns():
    nmcli_ovs_interface = (
        "nmcli",
        "connection",
        "add",
        "type",
        "ovs-interface",
        "slave-type",
        "ovs-port",
        "conn.interface",
        "br-ex",
        "master",
        "ovs-port-br-ex",
        "con-name",
        "ovs-if-br-ex",
        "ipv4.method",
        "manual",
        "ipv4.addr",
        "192.0.2.2/24",
        "ipv4.dns",
        "192.0.2.1",
        "ipv4.routes",
        "0.0.0.0/0 192.0.2.1",
    )
    cmdlib.exec_cmd(nmcli_ovs_interface, check=True)


def _verify_ovs_activated(ovs_name):
    ret, out, err = cmdlib.exec_cmd(
        f"nmcli --field GENERAL.STATE device show {ovs_name}".split(),
        check=True,
    )
    connected = "connected" in out
    ret, out, err = cmdlib.exec_cmd(
        f"nmcli --field IP4.ADDRESS device show {ovs_name}".split(),
        check=True,
    )
    ipv4_configured = "192.0.2.2/24" in out
    ret, out, err = cmdlib.exec_cmd(
        f"nmcli --field IP4.ROUTE device show {ovs_name}".split(),
        check=True,
    )
    route_configured = "0.0.0.0/0" in out
    return connected and ipv4_configured and route_configured


@pytest.fixture
def ovs_bridge_first_and_ovs_interface_with_same_name_ipv4():
    # The order on this function is important. The OVS bridge must be defined
    # before the OVS interface.
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-port conn.interface br-ex master br-ex "
        "con-name ovs-port-br-ex".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-bridge con-name br-ex conn.interface "
        "br-ex".split(),
        check=True,
    )
    _nmcli_ovs_bridge_with_ipv4_dns()
    # Wait a little bit for NM to activate above interfaces to do not hit race
    # problems.
    assert retry_till_true_or_timeout(
        VERIFY_RETRY_TMO, _verify_ovs_activated, OVS_DUP_NAME
    )
    yield
    cmdlib.exec_cmd(
        "nmcli connection del ovs-port-br-ex br-ex ovs-if-br-ex".split(),
        check=True,
    )


@pytest.fixture
def ovs_interface_first_and_ovs_bridge_with_same_name_ipv4():
    # The order on this function is important. The OVS interface must be
    # defined before the OVS bridge.
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-port conn.interface br-ex master br-ex "
        "con-name ovs-port-br-ex".split(),
        check=True,
    )
    _nmcli_ovs_bridge_with_ipv4_dns()
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-bridge con-name br-ex conn.interface "
        "br-ex".split(),
        check=True,
    )
    # Wait a little bit for NM to activate above interfaces to do not hit race
    # problems.
    assert retry_till_true_or_timeout(
        VERIFY_RETRY_TMO, _verify_ovs_activated, OVS_DUP_NAME
    )
    yield
    cmdlib.exec_cmd(
        "nmcli connection del ovs-port-br-ex br-ex ovs-if-br-ex".split(),
        check=True,
    )


@pytest.mark.tier1
def test_modify_state_with_ovs_dup_name_ovs_bridge_first_with_ipv4_dns(
    ovs_bridge_first_and_ovs_interface_with_same_name_ipv4,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ETH1,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)


@pytest.mark.tier1
def test_modify_state_with_ovs_dup_name_ovs_interface_first_with_ipv4_dns(
    ovs_interface_first_and_ovs_bridge_with_same_name_ipv4,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ETH1,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_remove_ovs_bridge_and_modify_ports(bridge_with_ports):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE0,
                Interface.STATE: InterfaceState.ABSENT,
            },
            {
                Interface.NAME: IFACE0,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                Interface.STATE: InterfaceState.UP,
                Interface.MTU: 2000,
            },
            {
                Interface.NAME: BRIDGE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                OVSBridge.CONFIG_SUBTREE: {
                    OVSBridge.PORT_SUBTREE: [{OVSBridge.Port.NAME: IFACE0}]
                },
            },
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)
    finally:
        absent_state = {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
        libnmstate.apply(absent_state)


@pytest.mark.tier1
def test_remove_ovs_bridge_clean_up_system_port_also(bridge_with_ports):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )

    _, output, _ = cmdlib.exec_cmd(
        "nmcli -g connection.master c show eth1".split()
    )
    assert not output.strip()


@pytest.fixture
def bridge_with_eth1_and_same_name_iface(eth1_up):
    bridge = Bridge(BRIDGE0)
    bridge.add_system_port(ETH1)
    bridge.add_internal_port(
        BRIDGE0, ipv4_state={InterfaceIPv4.ENABLED: False}
    )
    with bridge.create():
        yield bridge


@pytest.mark.tier1
def test_remove_same_name_ovs_bridge_clean_up_system_port_also(
    bridge_with_eth1_and_same_name_iface,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )

    _, output, _ = cmdlib.exec_cmd(
        "nmcli -g connection.master c show eth1".split()
    )
    assert not output.strip()


@pytest.mark.tier1
def test_purge_unmanged_ovs_bridge_in_show(ovs_unmanaged_bridge):
    state = statelib.show_only((BRIDGE0,))
    assert len(state[Interface.KEY]) == 1
    assert state[Interface.KEY][0][Interface.NAME] == BRIDGE0
    assert (
        state[Interface.KEY][0][Interface.TYPE] == InterfaceType.OVS_INTERFACE
    )


def get_nm_conn_timestamp(conn_name):
    output = cmdlib.exec_cmd(
        f"nmcli -g connection.timestamp c show {conn_name}".split(), check=True
    )[1]
    return int(output)


def get_nm_conn_uuid(conn_name):
    output = cmdlib.exec_cmd(
        f"nmcli -g connection.uuid c show {conn_name}".split(), check=True
    )[1]
    return output


def test_do_not_touch_ovs_port_when_not_desired_system_iface(
    bridge_with_ports,
):
    """
    The modification like MTU of ovs system interface should not reactivate its
    OVS port
    """
    old_timestamp = get_nm_conn_timestamp("eth1-port")
    old_uuid = get_nm_conn_uuid("eth1-port")

    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.MTU: 2000,
            },
        ]
    }
    libnmstate.apply(desired_state)

    new_uuid = get_nm_conn_uuid("eth1-port")
    new_timestamp = get_nm_conn_timestamp("eth1-port")

    assert old_timestamp == new_timestamp
    assert old_uuid == new_uuid


def test_do_not_touch_ovs_port_when_not_desired_internal_iface(
    bridge_with_ports,
):
    """
    The modification like MTU of ovs internal interface should not reactivate
    its OVS port
    """
    old_timestamp = get_nm_conn_timestamp(f"{IFACE0}-port")
    old_uuid = get_nm_conn_uuid(f"{IFACE0}-port")

    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: IFACE0,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                Interface.STATE: InterfaceState.UP,
                Interface.MTU: 2000,
            },
        ]
    }
    libnmstate.apply(desired_state)

    new_timestamp = get_nm_conn_timestamp(f"{IFACE0}-port")
    new_uuid = get_nm_conn_uuid(f"{IFACE0}-port")

    assert old_timestamp == new_timestamp
    assert old_uuid == new_uuid
