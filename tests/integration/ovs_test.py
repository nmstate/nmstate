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

import pytest

import libnmstate
from libnmstate.prettystate import PrettyState
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import OvsDB
from libnmstate.schema import OVSInterface
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateNotSupportedError
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
BRIDGE0 = "br0"
BRIDGE1 = "br1"
PORT1 = "ovs1"
PORT2 = "ovs2"
PATCH0 = "patch0"
PATCH1 = "patch1"
VLAN_IFNAME = "eth101"

MAC1 = "02:FF:FF:FF:FF:01"

ETH1 = "eth1"
ETH2 = "eth2"

OVS_BOND_YAML_STATE = f"""
    port:
    - name: {BOND1}
      link-aggregation:
        mode: active-backup
        slaves:
        - name: {ETH1}
        - name: {ETH2}
"""


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


class _OvsProfileStillExists(Exception):
    pass


@pytest.mark.tier1
@pytest.mark.xfail(
    reason="https://bugzilla.redhat.com/show_bug.cgi?id=1857123",
    raises=_OvsProfileStillExists,
    strict=False,
)
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

        rc, output, _ = cmdlib.exec_cmd(
            f"nmcli connection show {proxy_port_profile}".split(" "),
        )
        if rc == 0:
            raise _OvsProfileStillExists(
                f"{proxy_port_profile} still exists: {output}"
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
    def test_create_lag_with_ports_in_reverse_order(self, port0_up, port1_up):
        port0_name = port0_up[Interface.KEY][0][Interface.NAME]
        port1_name = port1_up[Interface.KEY][0][Interface.NAME]

        bridge = Bridge(BRIDGE1)
        bridge.add_link_aggregation_port(BOND1, (port1_name, port0_name))

        with bridge.create() as state:
            assertlib.assert_state_match(state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BOND1)

    def test_pretty_state_ovs_lag_name_first(self, eth1_up, eth2_up):
        bridge = Bridge(BRIDGE1)
        bridge.add_link_aggregation_port(BOND1, (ETH1, ETH2))

        with bridge.create():
            current_state = statelib.show_only((BRIDGE1,))
            pretty_state = PrettyState(current_state)
            assert OVS_BOND_YAML_STATE in pretty_state.yaml

    @pytest.mark.tier1
    def test_add_ovs_lag_to_existing_ovs_bridge(self, port0_up, port1_up):
        with Bridge(BRIDGE1).create():
            port0_name = port0_up[Interface.KEY][0][Interface.NAME]
            port1_name = port1_up[Interface.KEY][0][Interface.NAME]
            bridge = Bridge(BRIDGE1)
            bridge.add_link_aggregation_port(BOND1, (port1_name, port0_name))
            libnmstate.apply(bridge.state)
            assertlib.assert_state_match(bridge.state)


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


def test_ovsdb_new_bridge_with_external_id():
    bridge = Bridge(BRIDGE1)
    bridge.set_ovs_db({OvsDB.EXTERNAL_IDS: {"foo": "abc", "bak": 1}})
    bridge.add_internal_port(
        PORT1,
        ipv4_state={InterfaceIPv4.ENABLED: False},
        ovs_db={OvsDB.EXTERNAL_IDS: {"foo": "abcd", "bak": 2}},
    )
    with bridge.create() as state:
        assertlib.assert_state_match(state)
        new_state = statelib.show_only((PORT1,))
        # The newly created OVS internal interface should also hold
        # NM created external IDS.
        assert (
            "NM.connection.uuid"
            in new_state[Interface.KEY][0][OvsDB.OVS_DB_SUBTREE][
                OvsDB.EXTERNAL_IDS
            ]
        )


def test_ovsdb_set_external_ids_for_existing_bridge(bridge_with_ports):
    bridge = bridge_with_ports
    bridge.set_ovs_db({OvsDB.EXTERNAL_IDS: {"foo": "abc", "bak": 1}})
    bridge.add_internal_port(
        PORT2,
        ipv4_state={InterfaceIPv4.ENABLED: False},
        ovs_db={OvsDB.EXTERNAL_IDS: {"foo": "abcd", "bak": 2}},
    )
    bridge.apply()
    assertlib.assert_state_match(bridge.state)


@pytest.fixture
def ovs_bridge_with_custom_external_ids():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        PORT1,
        ipv4_state={InterfaceIPv4.ENABLED: False},
        ovs_db={OvsDB.EXTERNAL_IDS: {"foo": "abcd", "bak": 2}},
    )
    with bridge.create() as state:
        yield state


def test_ovsdb_remove_external_ids(ovs_bridge_with_custom_external_ids):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: PORT1,
                    OvsDB.OVS_DB_SUBTREE: {OvsDB.EXTERNAL_IDS: {}},
                }
            ]
        }
    )
    iface_info = statelib.show_only((PORT1,))[Interface.KEY][0]
    external_ids = iface_info[OvsDB.OVS_DB_SUBTREE][OvsDB.EXTERNAL_IDS]
    assert len(external_ids) == 1


def test_ovsdb_override_external_ids(ovs_bridge_with_custom_external_ids):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: PORT1,
                    OvsDB.OVS_DB_SUBTREE: {
                        OvsDB.EXTERNAL_IDS: {"new_ids": "haha"}
                    },
                }
            ]
        }
    )
    iface_info = statelib.show_only((PORT1,))[Interface.KEY][0]
    external_ids = iface_info[OvsDB.OVS_DB_SUBTREE][OvsDB.EXTERNAL_IDS]
    assert len(external_ids) == 2
    assert external_ids["new_ids"] == "haha"


def test_ovsdb_preserved_if_not_mentioned(ovs_bridge_with_custom_external_ids):
    libnmstate.apply(
        {Interface.KEY: [{Interface.NAME: PORT1, Interface.MTU: 1501}]}
    )
    iface_info = statelib.show_only((PORT1,))[Interface.KEY][0]
    external_ids = iface_info[OvsDB.OVS_DB_SUBTREE][OvsDB.EXTERNAL_IDS]
    assert len(external_ids) > 1


class TestOvsPatch:
    def test_create_and_remove_patch_port(self):
        patch0_state = {OVSInterface.Patch.PEER: "patch1"}
        patch1_state = {OVSInterface.Patch.PEER: "patch0"}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PATCH0, patch_state=patch0_state)
        desired_state = bridge.state
        bridge = Bridge(BRIDGE1)
        bridge.add_internal_port(PATCH1, patch_state=patch1_state)
        desired_state[Interface.KEY].extend(bridge.state[Interface.KEY])
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
        finally:
            for iface in desired_state[Interface.KEY]:
                iface[Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BRIDGE0)
        assertlib.assert_absent(PATCH0)
        assertlib.assert_absent(PATCH1)

    def test_patch_interface_does_not_have_mtu(self):
        patch0_state = {OVSInterface.Patch.PEER: "patch1"}
        patch1_state = {OVSInterface.Patch.PEER: "patch0"}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PATCH0, patch_state=patch0_state)
        desired_state = bridge.state
        bridge = Bridge(BRIDGE1)
        bridge.add_internal_port(PATCH1, patch_state=patch1_state)
        desired_state[Interface.KEY].extend(bridge.state[Interface.KEY])
        try:
            libnmstate.apply(desired_state)
            patch0_state = statelib.show_only((PATCH0,))
            assert not patch0_state[Interface.KEY][0].get(Interface.MTU)
        finally:
            for iface in desired_state[Interface.KEY]:
                iface[Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

    def test_add_patch_to_existing_interface_invalid(self):
        patch0_state = {OVSInterface.Patch.PEER: "falsepatch"}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PATCH0)
        desired_state = bridge.state
        bridge = Bridge(BRIDGE1)
        bridge.add_internal_port(PATCH1)
        desired_state[Interface.KEY].extend(bridge.state[Interface.KEY])
        try:
            desired_state[Interface.KEY][1][
                OVSInterface.PATCH_CONFIG_SUBTREE
            ] = patch0_state
            desired_state[Interface.KEY][1][Interface.MTU] = 1500

            with pytest.raises(NmstateValueError):
                libnmstate.apply(desired_state)
        finally:
            for iface in desired_state[Interface.KEY]:
                iface[Interface.STATE] = InterfaceState.ABSENT
                iface[OVSInterface.PATCH_CONFIG_SUBTREE] = {}
            libnmstate.apply(desired_state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BRIDGE0)
        assertlib.assert_absent(PATCH0)
        assertlib.assert_absent(PATCH1)

    def test_add_patch_to_existing_interface_valid(self):
        patch0_state = {OVSInterface.Patch.PEER: "patch1"}
        patch1_state = {OVSInterface.Patch.PEER: "patch0"}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PATCH0)
        desired_state = bridge.state
        bridge = Bridge(BRIDGE1)
        bridge.add_internal_port(PATCH1)
        desired_state[Interface.KEY].extend(bridge.state[Interface.KEY])
        try:
            desired_state[Interface.KEY][1].pop(Interface.MTU, None)
            desired_state[Interface.KEY][1].pop(Interface.MAC, None)
            desired_state[Interface.KEY][1][
                OVSInterface.PATCH_CONFIG_SUBTREE
            ] = patch0_state
            desired_state[Interface.KEY][3].pop(Interface.MTU, None)
            desired_state[Interface.KEY][3].pop(Interface.MAC, None)
            desired_state[Interface.KEY][3][
                OVSInterface.PATCH_CONFIG_SUBTREE
            ] = patch1_state

            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
        finally:
            for iface in desired_state[Interface.KEY]:
                iface[Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BRIDGE0)
        assertlib.assert_absent(PATCH0)
        assertlib.assert_absent(PATCH1)


@pytest.mark.tier1
def test_create_internal_port_with_explict_mtu():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        PORT1,
        mac=MAC1,
        mtu=1501,
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


@pytest.mark.tier1
def test_change_mtu_of_existing_internal_port(bridge_with_ports):
    state = statelib.show_only((PORT1,))
    state[Interface.KEY][0][Interface.MTU] = 1501

    libnmstate.apply(state)

    assertlib.assert_state_match(state)


@pytest.mark.tier1
def test_create_ovs_with_internal_ports_in_reverse_order():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT2)
    bridge.add_internal_port(PORT1)

    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)
    assertlib.assert_absent(PORT2)


def test_create_memory_only_ovs_bridge_not_supported():
    bridge = Bridge(BRIDGE1)

    with pytest.raises(NmstateNotSupportedError):
        libnmstate.apply(bridge.state, save_to_disk=False)
