#
# Copyright (c) 2019-2022 Red Hat, Inc.
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
import os
import pytest

import libnmstate
from libnmstate.prettystate import PrettyState
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import MacVlan
from libnmstate.schema import MacVtap
from libnmstate.schema import OVSBridge
from libnmstate.schema import OVSInterface
from libnmstate.schema import OvsDB
from libnmstate.schema import RouteRule
from libnmstate.schema import VLAN
from libnmstate.schema import VXLAN
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateNotSupportedError
from libnmstate.error import NmstateValueError

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import iprule
from .testlib import statelib
from .testlib.env import nm_major_minor_version
from .testlib.nmplugin import disable_nm_plugin
from .testlib.nmplugin import mount_devnull_to_path
from .testlib.statelib import state_match
from .testlib.ovslib import Bridge
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
        port:
        - name: {ETH1}
        - name: {ETH2}
"""

RC_SUCCESS = 0
TEST_EXTERNAL_IDS_KEY = "ovn-bridge-mappings"
TEST_EXTERNAL_IDS_VALUE = "provider:br-provider"
TEST_OTHER_CONFIG_KEY = "stats-update-interval"
TEST_OTHER_CONFIG_VALUE = "1000"


def _test_pci_path():
    return os.environ.get("TEST_PCI_PATH")


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


@pytest.mark.tier1
def test_create_and_save_ovs_bridge_then_remove_and_apply_again():
    desired_state = {}
    with Bridge(BRIDGE1).create():
        desired_state = statelib.show_only((BRIDGE1,))

    assertlib.assert_absent(BRIDGE1)

    libnmstate.apply(desired_state)
    desired_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT

    libnmstate.apply(desired_state)
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


@pytest.mark.tier1
def test_create_ovs_bridge_with_internal_port_with_copy_mac_from(eth1_up):
    eth1_mac = eth1_up[Interface.KEY][0][Interface.MAC]

    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        PORT1, copy_mac_from=eth1_up[Interface.KEY][0][Interface.NAME]
    )
    bridge.add_system_port(ETH1)

    with bridge.create():
        current_state = statelib.show_only((PORT1,))
        assertlib.assert_mac_address(current_state, eth1_mac)


@pytest.fixture
def ovs_bridge1_with_internal_port_same_name():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(
        BRIDGE1, ipv4_state={InterfaceIPv4.ENABLED: False}
    )

    with bridge.create() as state:
        yield state


@pytest.mark.tier1
def test_create_and_remove_ovs_bridge1_with_internal_port_same_name(
    ovs_bridge1_with_internal_port_same_name,
):
    state = statelib.show_only((BRIDGE1,))
    assert state
    assert len(state[Interface.KEY]) == 2


@pytest.mark.tier1
def test_vlan_as_ovs_bridge_port(vlan_on_eth1):
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


def test_ovs_service_missing_with_system_port_only(eth1_up):
    bridge = Bridge(BRIDGE1)
    bridge.add_system_port(ETH1)

    with mount_devnull_to_path("/var/run/openvswitch/db.sock"):
        with pytest.raises(NmstateDependencyError):
            with bridge.create():
                pass


def test_ovs_service_missing_with_internal_port_only():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1)

    with mount_devnull_to_path("/var/run/openvswitch/db.sock"):
        with pytest.raises(NmstateDependencyError):
            with bridge.create():
                pass


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


def test_add_invalid_port_ip_config(eth1_up):
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
        # The newly created OVS internal interface should not hold
        # NM created external IDS.
        assert (
            "NM.connection.uuid"
            not in new_state[Interface.KEY][0][OvsDB.OVS_DB_SUBTREE][
                OvsDB.EXTERNAL_IDS
            ]
        )


def test_ovsdb_set_external_ids_for_ovs_system_interface(bridge_with_ports):
    system_port_name = "eth1"
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: system_port_name,
                Interface.TYPE: InterfaceType.ETHERNET,
                OvsDB.OVS_DB_SUBTREE: {OvsDB.EXTERNAL_IDS: {"foo": 1000}},
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


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
    assert len(external_ids) == 0


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
    assert len(external_ids) == 1
    assert external_ids["new_ids"] == "haha"


def test_ovsdb_preserved_if_not_mentioned(ovs_bridge_with_custom_external_ids):
    libnmstate.apply(
        {Interface.KEY: [{Interface.NAME: PORT1, Interface.MTU: 1501}]}
    )
    iface_info = statelib.show_only((PORT1,))[Interface.KEY][0]
    external_ids = iface_info[OvsDB.OVS_DB_SUBTREE][OvsDB.EXTERNAL_IDS]
    assert len(external_ids) > 1


def test_ovsdb_global_config_add_external_ids_and_remove():
    desired_ovs_config = {
        OvsDB.EXTERNAL_IDS: {TEST_EXTERNAL_IDS_KEY: TEST_EXTERNAL_IDS_VALUE}
    }
    libnmstate.apply({OvsDB.KEY: desired_ovs_config})
    current_ovs_config = libnmstate.show()[OvsDB.KEY]

    assert state_match(desired_ovs_config, current_ovs_config)

    libnmstate.apply(
        {OvsDB.KEY: {OvsDB.EXTERNAL_IDS: {TEST_EXTERNAL_IDS_KEY: None}}}
    )
    current_ovs_config = libnmstate.show()[OvsDB.KEY]

    assert TEST_EXTERNAL_IDS_KEY not in current_ovs_config[OvsDB.EXTERNAL_IDS]


def test_ovsdb_global_config_add_other_config_and_remove():
    desired_ovs_config = {
        OvsDB.OTHER_CONFIG: {TEST_OTHER_CONFIG_KEY: TEST_OTHER_CONFIG_VALUE}
    }
    libnmstate.apply({OvsDB.KEY: desired_ovs_config})
    current_ovs_config = libnmstate.show()[OvsDB.KEY]

    assert state_match(desired_ovs_config, current_ovs_config)

    libnmstate.apply(
        {OvsDB.KEY: {OvsDB.OTHER_CONFIG: {TEST_OTHER_CONFIG_KEY: None}}}
    )
    current_ovs_config = libnmstate.show()[OvsDB.KEY]

    assert TEST_OTHER_CONFIG_KEY not in current_ovs_config[OvsDB.OTHER_CONFIG]


def test_remove_all_ovsdb_global_config():
    libnmstate.apply({OvsDB.KEY: {}})
    current_ovs_config = libnmstate.show()[OvsDB.KEY]

    assert current_ovs_config == {
        OvsDB.EXTERNAL_IDS: {},
        OvsDB.OTHER_CONFIG: {},
    }


@pytest.fixture
def ovsdb_global_config_external_ids():
    ovs_config = {
        OvsDB.EXTERNAL_IDS: {TEST_EXTERNAL_IDS_KEY: TEST_EXTERNAL_IDS_VALUE}
    }
    libnmstate.apply({OvsDB.KEY: ovs_config})
    yield ovs_config
    libnmstate.apply(
        {OvsDB.KEY: {OvsDB.EXTERNAL_IDS: {TEST_EXTERNAL_IDS_KEY: None}}}
    )


def test_ovsdb_global_config_untouched_if_not_defined(
    ovsdb_global_config_external_ids,
):
    desired_ovs_config = ovsdb_global_config_external_ids
    libnmstate.apply({})

    current_ovs_config = libnmstate.show()[OvsDB.KEY]
    assert state_match(desired_ovs_config, current_ovs_config)


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


def test_create_memory_only_ovs_bridge():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1)

    if nm_major_minor_version() <= 1.28:
        with pytest.raises(NmstateNotSupportedError):
            libnmstate.apply(bridge.state, save_to_disk=False)
    else:
        try:
            libnmstate.apply(bridge.state, save_to_disk=False)
        finally:
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


def test_remove_all_ovs_ports(bridge_with_ports):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE1,
                    OVSBridge.CONFIG_SUBTREE: {OVSBridge.PORT_SUBTREE: []},
                }
            ]
        }
    )
    assertlib.assert_absent(PORT1)


def test_modify_state_do_not_remove_unmanaged_ovs(eth1_up):
    with unmanaged_ovs_bridge():
        eth1_up[Interface.KEY][0][Interface.MTU] = 1400
        libnmstate.apply(eth1_up)
        current_state = statelib.show_only((BRIDGE0,))
        assert len(current_state[Interface.KEY])
        assert current_state[Interface.KEY][0][Interface.NAME] == BRIDGE0


@contextmanager
def unmanaged_ovs_bridge():
    rc, _, _ = cmdlib.exec_cmd(
        "ovs-vsctl add-br br0 -- set Bridge br0 fail-mode=secure".split(),
        check=True,
    )
    assert rc == RC_SUCCESS
    try:
        yield
    finally:
        rc, _, _ = cmdlib.exec_cmd("ovs-vsctl del-br br0".split(), check=True)
        assert rc == RC_SUCCESS


def test_expect_failure_when_create_ovs_interface_without_bridge():
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "ovs0",
                        Interface.TYPE: InterfaceType.OVS_INTERFACE,
                        Interface.STATE: InterfaceState.UP,
                    }
                ]
            }
        )


@pytest.mark.tier1
def test_create_vlan_over_ovs_iface_with_use_same_name_as_bridge(
    ovs_bridge1_with_internal_port_same_name,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "vlan101",
                Interface.TYPE: InterfaceType.VLAN,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: BRIDGE1},
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_create_vxlan_over_ovs_iface_with_use_same_name_as_bridge(
    ovs_bridge1_with_internal_port_same_name,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "vlan101",
                Interface.TYPE: InterfaceType.VXLAN,
                VXLAN.CONFIG_SUBTREE: {
                    VXLAN.ID: 101,
                    VXLAN.BASE_IFACE: BRIDGE1,
                    VXLAN.REMOTE: "192.0.2.251",
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_create_mac_vlan_over_ovs_iface_with_use_same_name_as_bridge(
    ovs_bridge1_with_internal_port_same_name,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "mac_vlan101",
                Interface.TYPE: InterfaceType.MAC_VLAN,
                MacVlan.CONFIG_SUBTREE: {
                    MacVlan.BASE_IFACE: BRIDGE1,
                    MacVlan.MODE: MacVlan.Mode.PASSTHRU,
                    MacVlan.PROMISCUOUS: False,
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_create_mac_tap_over_ovs_iface_with_use_same_name_as_bridge(
    ovs_bridge1_with_internal_port_same_name,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "mac_tap0",
                Interface.TYPE: InterfaceType.MAC_VTAP,
                MacVtap.CONFIG_SUBTREE: {
                    MacVtap.BASE_IFACE: BRIDGE1,
                    MacVtap.MODE: MacVtap.Mode.PASSTHRU,
                    MacVtap.PROMISCUOUS: False,
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_ignore_ovs_system_kernel_nic(bridge_with_ports):
    assert not statelib.show_only(("ovs-system",))[Interface.KEY]


@pytest.mark.tier1
def test_set_static_to_ovs_interface_with_the_same_name_bridge(
    ovs_bridge1_with_internal_port_same_name,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: "192.0.2.1",
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    state = statelib.show_only((BRIDGE1,))
    assert len(state[Interface.KEY]) == 2
    cur_iface_state = None
    for iface in state[Interface.KEY]:
        if iface[Interface.TYPE] == InterfaceType.OVS_INTERFACE:
            cur_iface_state = iface
            break
    assert cur_iface_state
    assert cur_iface_state[Interface.IPV4][InterfaceIPv4.ADDRESS] == [
        {
            InterfaceIPv4.ADDRESS_IP: "192.0.2.1",
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
        }
    ]


@pytest.fixture
def ovs_bridge_with_dhcp_route_table_500(bridge_with_ports):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: PORT1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.AUTO_ROUTE_TABLE_ID: 500,
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    yield


@pytest.mark.tier1
def test_add_route_rule_to_ovs_interface_dhcp_auto_route_table(
    ovs_bridge_with_dhcp_route_table_500,
):
    route_rule = {
        RouteRule.IP_FROM: "192.0.2.0/24",
        RouteRule.ROUTE_TABLE: 500,
    }
    desired_state = {RouteRule.KEY: {RouteRule.CONFIG: [route_rule]}}
    libnmstate.apply(desired_state)

    iprule.ip_rule_exist_in_os(
        route_rule.get(RouteRule.IP_FROM),
        route_rule.get(RouteRule.IP_TO),
        route_rule.get(RouteRule.PRIORITY),
        route_rule.get(RouteRule.ROUTE_TABLE),
    )


@pytest.mark.skipif(
    not os.environ.get("TEST_PCI_PATH"),
    reason="Need to define TEST_PCI_PATH for OVS DPDK tests.",
)
class TestOvsDpdk:
    def test_create_ovs_dpdk_and_remove(self, setup_ovs_dpdk):
        dpdk0_state = {OVSInterface.Dpdk.DEVARGS: _test_pci_path()}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PORT1, dpdk_state=dpdk0_state)
        desired_state = bridge.state
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
        finally:
            for iface in desired_state[Interface.KEY]:
                iface[Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

        assertlib.assert_absent(BRIDGE0)
        assertlib.assert_absent(PORT1)

    @pytest.mark.parametrize("datapaths", ("netdev", "system"))
    def test_create_ovs_dpdk_with_datapath(self, setup_ovs_dpdk, datapaths):
        dpdk0_state = {OVSInterface.Dpdk.DEVARGS: _test_pci_path()}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PORT1, dpdk_state=dpdk0_state)
        bridge.set_options({OVSBridge.Options.DATAPATH: datapaths})
        desired_state = bridge.state
        try:
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)
        finally:
            for iface in desired_state[Interface.KEY]:
                iface[Interface.STATE] = InterfaceState.ABSENT
            libnmstate.apply(desired_state)

        assertlib.assert_absent(BRIDGE0)
        assertlib.assert_absent(PORT1)
