# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager
import os
import pytest
import yaml

import libnmstate
from libnmstate.prettystate import PrettyState
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge
from libnmstate.schema import MacVlan
from libnmstate.schema import MacVtap
from libnmstate.schema import OVSBridge
from libnmstate.schema import OVSInterface
from libnmstate.schema import OvsDB
from libnmstate.schema import Ovn
from libnmstate.schema import RouteRule
from libnmstate.schema import VLAN
from libnmstate.schema import VXLAN
from libnmstate.schema import Veth
from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateNotSupportedError
from libnmstate.error import NmstateValueError

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import iprule
from .testlib import statelib
from .testlib.bondlib import bond_interface
from .testlib.bridgelib import linux_bridge
from .testlib.env import is_k8s
from .testlib.env import nm_major_minor_version
from .testlib.env import nm_minor_version
from .testlib.genconf import gen_conf_apply
from .testlib.nmplugin import disable_nm_plugin
from .testlib.ovslib import Bridge
from .testlib.retry import retry_till_true_or_timeout
from .testlib.servicelib import disable_service
from .testlib.statelib import state_match
from .testlib.vlan import vlan_interface


BOND1 = "bond1"
BRIDGE0 = "br0"
BRIDGE1 = "br1"
PORT1 = "ovs1"
PORT2 = "ovs2"
PATCH0 = "patch0"
PATCH1 = "patch1"
VLAN_IFNAME = "eth101"
VETH1 = "test-veth1"
VETH1_PEER = "test-veth1-ep"

MAC1 = "02:FF:FF:FF:FF:01"

ETH1 = "eth1"
ETH2 = "eth2"

EMPTY_MAP = "{}"

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
TEST_OVN_MAPPINGS_BRIDGE = "br-provider"
TEST_OVN_MAPPINGS_PHYSNET = "provider"
TEST_EXTERNAL_IDS_KEY = "akey"
TEST_EXTERNAL_IDS_VALUE = "aval"
TEST_EXTERNAL_IDS_MAPPING_KEY = "ovn-bridge-mappings"
TEST_EXTERNAL_IDS_MAPPING_VALUE = (
    f"{TEST_OVN_MAPPINGS_PHYSNET}:{TEST_OVN_MAPPINGS_BRIDGE}"
)
TEST_OTHER_CONFIG_KEY = "stats-update-interval"
TEST_OTHER_CONFIG_VALUE = "1000"
RETRY_TIMEOUT = 15


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
    with Bridge(BRIDGE1).create():
        # assert_state_match does not works well when ovs bridge and ovs
        # interface are using the same name.
        cur_state = statelib.show_only((BRIDGE1,))
        assert len(cur_state[Interface.KEY]) == 2

    assertlib.assert_absent(BRIDGE1)


@pytest.mark.tier1
def test_create_and_save_ovs_bridge_then_remove_and_apply_again():
    desired_state = {}
    with Bridge(BRIDGE1).create():
        desired_state = statelib.show_only((BRIDGE1,))

    assertlib.assert_absent(BRIDGE1)

    libnmstate.apply(desired_state)
    desired_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
    desired_state[Interface.KEY][1][Interface.STATE] = InterfaceState.ABSENT

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

    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
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
def test_create_and_modify_ovs_bridge1_with_internal_port_same_name(
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
            },
            {
                Interface.NAME: BRIDGE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                Interface.STATE: InterfaceState.UP,
                OVSBridge.CONFIG_SUBTREE: {
                    OVSBridge.PORT_SUBTREE: [
                        {
                            OVSBridge.Port.NAME: BRIDGE1,
                        },
                    ]
                },
            },
        ]
    }
    libnmstate.apply(desired_state)


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
        bridge.add_link_aggregation_port(
            BOND1,
            (ETH1, ETH2),
            mode=OVSBridge.Port.LinkAggregation.Mode.ACTIVE_BACKUP,
        )

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
    def test_add_ovs_lag_with_updelay_and_downdelay(self, port0_up, port1_up):
        port0_name = port0_up[Interface.KEY][0][Interface.NAME]
        port1_name = port1_up[Interface.KEY][0][Interface.NAME]

        bridge = Bridge(BRIDGE1)
        bridge.add_link_aggregation_port(
            BOND1,
            (port0_name, port1_name),
            mode="active-backup",
            updelay=1000,
            downdelay=1000,
        )

        with bridge.create() as state:
            assertlib.assert_state_match(state)

        assertlib.assert_absent(BRIDGE1)
        assertlib.assert_absent(BOND1)

    @pytest.mark.tier1
    def test_modify_ovs_lag_with_updelay_and_downdelay(
        self, port0_up, port1_up
    ):
        port0_name = port0_up[Interface.KEY][0][Interface.NAME]
        port1_name = port1_up[Interface.KEY][0][Interface.NAME]

        bridge = Bridge(BRIDGE1)
        bridge.add_link_aggregation_port(
            BOND1,
            (port0_name, port1_name),
            mode="active-backup",
            updelay=1000,
            downdelay=1000,
        )

        with bridge.create() as state:
            assertlib.assert_state_match(state)
            state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE][
                OVSBridge.PORT_SUBTREE
            ][0][OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
                OVSBridge.Port.LinkAggregation.Options.DOWN_DELAY
            ] = 100
            state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE][
                OVSBridge.PORT_SUBTREE
            ][0][OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
                OVSBridge.Port.LinkAggregation.Options.UP_DELAY
            ] = 100
            libnmstate.apply(state)
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


@pytest.fixture
def bridge_port_with_trunks():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
    bridge.set_port_option(
        PORT1,
        {
            OVSBridge.Port.NAME: PORT1,
            OVSBridge.Port.VLAN_SUBTREE: {
                OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.TRUNK,
                OVSBridge.Port.Vlan.TAG: 0,
                OVSBridge.Port.Vlan.TRUNK_TAGS: [
                    {OVSBridge.Port.Vlan.TrunkTags.ID: 10},
                    {OVSBridge.Port.Vlan.TrunkTags.ID: 20},
                    {
                        OVSBridge.Port.Vlan.TrunkTags.ID_RANGE: {
                            OVSBridge.Port.Vlan.TrunkTags.MIN_RANGE: 30,
                            OVSBridge.Port.Vlan.TrunkTags.MAX_RANGE: 40,
                        }
                    },
                ],
            },
        },
    )
    with bridge.create() as state:
        yield state
    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 41,
    reason="OVS VLAN trunks was not supported in NM",
)
def test_ovs_vlan_trunks(bridge_port_with_trunks):
    assertlib.assert_state_match(bridge_port_with_trunks)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 41,
    reason="OVS VLAN trunks was not supported in NM",
)
def test_remove_ovs_vlan_trunks(bridge_port_with_trunks):
    br1_state = statelib.show_only((BRIDGE1,))[Interface.KEY][0]
    port_state = br1_state[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE][0]
    trunks = port_state[OVSBridge.Port.VLAN_SUBTREE][
        OVSBridge.Port.Vlan.TRUNK_TAGS
    ]
    assert len(trunks) == 3

    bridge_config = bridge_port_with_trunks[Interface.KEY][0][
        OVSBridge.CONFIG_SUBTREE
    ]
    port_config = bridge_config[OVSBridge.PORT_SUBTREE][0]
    port_config.update(
        {
            OVSBridge.Port.VLAN_SUBTREE: {
                OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.TRUNK,
                OVSBridge.Port.Vlan.TAG: 0,
                OVSBridge.Port.Vlan.TRUNK_TAGS: [],
            }
        }
    )
    libnmstate.apply(bridge_port_with_trunks)
    assertlib.assert_state(bridge_port_with_trunks)

    br1_state = statelib.show_only((BRIDGE1,))[Interface.KEY][0]
    port_state = br1_state[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE][0]
    trunks = port_state[OVSBridge.Port.VLAN_SUBTREE][
        OVSBridge.Port.Vlan.TRUNK_TAGS
    ]
    assert len(trunks) == 0


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
    assert OvsDB.OVS_DB_SUBTREE not in iface_info


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


def test_ovsdb_global_config_add_delete_mapping():
    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.BRIDGE: "br1",
                Ovn.BridgeMappings.STATE: "present",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: desired_ovs_config})
    current_ovs_config = libnmstate.show()[Ovn.KEY]

    assert state_match(desired_ovs_config, current_ovs_config)

    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.BRIDGE: "br1",
                Ovn.BridgeMappings.STATE: "absent",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: desired_ovs_config})
    assert Ovn.OVN_SUBTREE not in libnmstate.show()


@pytest.fixture
def ovn_bridge_mapping_net1():
    ovn_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.BRIDGE: "br1",
                Ovn.BridgeMappings.STATE: "present",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: ovn_config})
    yield ovn_config
    libnmstate.apply(
        {
            Ovn.KEY: {
                Ovn.BRIDGE_MAPPINGS: [
                    {
                        Ovn.BridgeMappings.LOCALNET: "net1",
                        Ovn.BridgeMappings.STATE: "absent",
                    },
                ]
            }
        }
    )


@pytest.fixture
def ovn_bridge_mapping_net2():
    ovn_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net2",
                Ovn.BridgeMappings.BRIDGE: "br2",
                Ovn.BridgeMappings.STATE: "present",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: ovn_config})
    yield ovn_config
    libnmstate.apply(
        {
            Ovn.KEY: {
                Ovn.BRIDGE_MAPPINGS: [
                    {
                        Ovn.BridgeMappings.LOCALNET: "net1",
                        Ovn.BridgeMappings.STATE: "absent",
                    },
                ]
            }
        }
    )


def test_ovn_global_config_add_delete_single_mapping(ovn_bridge_mapping_net1):
    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net123",
                Ovn.BridgeMappings.BRIDGE: "br321",
                Ovn.BridgeMappings.STATE: "present",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: desired_ovs_config})
    current_ovs_config = libnmstate.show()[Ovn.KEY]

    desired_ovs_config[Ovn.BRIDGE_MAPPINGS] += ovn_bridge_mapping_net1[
        Ovn.BRIDGE_MAPPINGS
    ]
    desired_ovs_config[Ovn.BRIDGE_MAPPINGS] = sorted(
        desired_ovs_config[Ovn.BRIDGE_MAPPINGS],
        key=lambda mapping: mapping[Ovn.BridgeMappings.LOCALNET],
    )
    assert state_match(
        desired_ovs_config,
        current_ovs_config,
    )

    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net123",
                Ovn.BridgeMappings.STATE: "absent",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: desired_ovs_config})
    assert libnmstate.show()[Ovn.KEY] == ovn_bridge_mapping_net1


def test_ovn_global_config_modify_and_delete_mappings(
    ovn_bridge_mapping_net1, ovn_bridge_mapping_net2
):
    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.BRIDGE: "br321",
            },
            {
                Ovn.BridgeMappings.LOCALNET: "net2",
                Ovn.BridgeMappings.STATE: "absent",
            },
        ]
    }
    libnmstate.apply({Ovn.KEY: desired_ovs_config})
    current_ovs_config = libnmstate.show()[Ovn.KEY]
    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.BRIDGE: "br321",
            },
        ]
    }
    assert state_match(desired_ovs_config, current_ovs_config)


def test_ovsdb_global_config_cannot_use_ovn_bridge_mappings_external_id():
    desired_ovs_config = {
        OvsDB.EXTERNAL_IDS: {
            TEST_EXTERNAL_IDS_MAPPING_KEY: TEST_EXTERNAL_IDS_MAPPING_VALUE,
        }
    }
    with pytest.raises(NmstateValueError):
        libnmstate.apply({OvsDB.KEY: desired_ovs_config})


def test_ovsdb_global_config_clearing_ext_ids_preserves_existing_mappings(
    ovn_bridge_mapping_net1,
):
    desired_ovs_config = {
        OvsDB.EXTERNAL_IDS: {},
    }
    libnmstate.apply({OvsDB.KEY: desired_ovs_config})
    current_ovs_config = libnmstate.show()[Ovn.KEY]

    assert current_ovs_config == ovn_bridge_mapping_net1


def test_ovn_bridge_mappings_cannot_have_duplicate_localnet_keys():
    desired_ovs_config = {
        Ovn.BRIDGE_MAPPINGS: [
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.BRIDGE: "br321",
            },
            {
                Ovn.BridgeMappings.LOCALNET: "net1",
                Ovn.BridgeMappings.STATE: "absent",
            },
        ]
    }
    with pytest.raises(NmstateValueError):
        libnmstate.apply({Ovn.KEY: desired_ovs_config})


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


def test_mappings_update_does_not_clear_other_ext_ids(
    ovsdb_global_config_external_ids,
    ovn_bridge_mapping_net1,
):
    current_ovs_config = libnmstate.show()[OvsDB.KEY]
    assert current_ovs_config.pop(OvsDB.OTHER_CONFIG) == {}
    assert (
        ovsdb_global_config_external_ids[OvsDB.EXTERNAL_IDS].items()
        <= current_ovs_config[OvsDB.EXTERNAL_IDS].items()
    )

    current_ovn_config = libnmstate.show()[Ovn.KEY]
    assert current_ovn_config == ovn_bridge_mapping_net1


def test_ovsdb_global_config_untouched_if_not_defined(
    ovsdb_global_config_external_ids,
):
    desired_ovs_config = ovsdb_global_config_external_ids
    libnmstate.apply({})

    current_ovs_config = libnmstate.show()[OvsDB.KEY]
    assert state_match(desired_ovs_config, current_ovs_config)


@pytest.fixture
def ovs_bridge_with_patch_ports():
    patch0_state = {OVSInterface.Patch.PEER: "patch1"}
    patch1_state = {OVSInterface.Patch.PEER: "patch0"}
    bridge = Bridge(BRIDGE0)
    bridge.add_internal_port(PATCH0, patch_state=patch0_state)
    desired_state = bridge.state
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PATCH1, patch_state=patch1_state)
    desired_state[Interface.KEY].extend(bridge.state[Interface.KEY])
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)
    yield
    for iface in desired_state[Interface.KEY]:
        iface[Interface.STATE] = InterfaceState.ABSENT
    libnmstate.apply(desired_state)
    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(BRIDGE0)
    assertlib.assert_absent(PATCH0)
    assertlib.assert_absent(PATCH1)


class TestOvsPatch:
    def test_create_and_remove_patch_port(self, ovs_bridge_with_patch_ports):
        pass

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

    def test_change_ovsdb_ext_id_of_ovs_path(
        self, ovs_bridge_with_patch_ports
    ):
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: PATCH0,
                        OvsDB.KEY: {
                            "foo": "abc",
                        },
                    },
                    {
                        Interface.NAME: PATCH1,
                        OvsDB.KEY: {
                            "foo": "abd",
                        },
                    },
                ]
            }
        )


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

    def _ovs_iface_got_ip():
        state = statelib.show_only((BRIDGE1,))
        if len(state[Interface.KEY]) != 2:
            return False
        cur_iface_state = None
        for iface in state[Interface.KEY]:
            if iface[Interface.TYPE] == InterfaceType.OVS_INTERFACE:
                cur_iface_state = iface
                break
        return cur_iface_state and cur_iface_state[Interface.IPV4][
            InterfaceIPv4.ADDRESS
        ] == [
            {
                InterfaceIPv4.ADDRESS_IP: "192.0.2.1",
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ]

    assert retry_till_true_or_timeout(RETRY_TIMEOUT, _ovs_iface_got_ip)


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

    iprule.ip_rule_exist_in_os(route_rule)


@pytest.fixture
def cleanup_ovs_bridge_and_bond():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: BOND1,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


@pytest.mark.tier1
def test_attach_linux_bond_to_ovs_bridge(
    cleanup_ovs_bridge_and_bond, eth1_up, eth2_up
):
    desired_state = yaml.load(
        """---
        interfaces:
          - name: bond1
            state: up
            type: bond
            link-aggregation:
              mode: active-backup
              options:
                miimon: 140
                primary: eth1
              port:
                - eth1
                - eth2
          - name: br0
            type: ovs-bridge
            state: up
            bridge:
              options:
                stp: false
              port:
                - name: bond1
            """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.mark.skipif(
    not os.environ.get("TEST_PCI_PATH"),
    reason="Need to define TEST_PCI_PATH for OVS DPDK tests.",
)
class TestOvsDpdk:
    def test_create_ovs_dpdk_and_remove(self):
        dpdk0_state = {OVSInterface.Dpdk.DEVARGS: _test_pci_path()}
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PORT1, dpdk_state=dpdk0_state)
        bridge.set_options({OVSBridge.Options.DATAPATH: "netdev"})
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

    @pytest.mark.tier1
    def test_create_ovs_dpdk_with_rx_queue(self):
        dpdk0_state = {
            OVSInterface.Dpdk.DEVARGS: _test_pci_path(),
            OVSInterface.Dpdk.RX_QUEUE: 10,
        }
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PORT1, dpdk_state=dpdk0_state)
        bridge.set_options({OVSBridge.Options.DATAPATH: "netdev"})
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
    def test_create_ovs_dpdk_with_datapath(self, datapaths):
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

    def test_create_ovs_dpdk_queue_descriptor(self, datapaths):
        dpdk0_state = {
            OVSInterface.Dpdk.DEVARGS: _test_pci_path(),
            OVSInterface.Dpdk.N_RXQ_DESC: 1024,
            OVSInterface.Dpdk.N_TXQ_DESC: 2048,
        }
        bridge = Bridge(BRIDGE0)
        bridge.add_internal_port(PORT1, dpdk_state=dpdk0_state)
        bridge.set_options({OVSBridge.Options.DATAPATH: "netdev"})
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


@pytest.fixture
def unmanged_ovs_vxlan():
    cmdlib.exec_cmd("ovs-vsctl add-br br0_with_vxlan".split(), check=True)
    cmdlib.exec_cmd(
        "ovs-vsctl add-port br0_with_vxlan vx_node1 -- "
        "set interface vx_node1 type=vxlan options:remote_ip=192.168.122.174 "
        "options:dst_port=8472".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        "nmcli d set vxlan_sys_8472 managed false".split(), check=True
    )
    try:
        yield
    finally:
        cmdlib.exec_cmd("ovs-vsctl del-br br0_with_vxlan".split())


@pytest.mark.tier1
def test_ovs_vxlan_in_current_not_impact_others(unmanged_ovs_vxlan):
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)


def test_add_new_ovs_interface_to_existing(bridge_with_ports):
    bridge = bridge_with_ports
    bridge.add_internal_port(
        PORT2,
        ipv4_state={InterfaceIPv4.ENABLED: False},
    )
    bridge.apply()
    assertlib.assert_state_match(bridge.state)


@pytest.fixture
def clean_new_veth():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {Interface.NAME: VETH1, Interface.STATE: InterfaceState.ABSENT}
            ]
        }
    )


def test_add_new_sys_veth_interface_to_existing_ovs_bridge(
    bridge_with_ports, clean_new_veth
):
    bridge = bridge_with_ports
    bridge.add_system_port(VETH1)
    desired_state = bridge.state
    desired_state[Interface.KEY].append(
        {
            Interface.NAME: VETH1,
            Interface.TYPE: InterfaceType.VETH,
            Veth.CONFIG_SUBTREE: {
                Veth.PEER: VETH1_PEER,
            },
        }
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.fixture
def ovsdb_global_db():
    original = libnmstate.show()[OvsDB.KEY]
    libnmstate.apply(
        {
            OvsDB.KEY: {
                OvsDB.EXTERNAL_IDS: {
                    "opt1": "value1",
                    "opt2": "value2",
                },
                OvsDB.OTHER_CONFIG: {
                    "flow-restore-wait": "true",
                },
            }
        }
    )
    yield
    libnmstate.apply({OvsDB.KEY: {}})
    libnmstate.apply({OvsDB.KEY: original})


def test_ovsdb_global_merged_desired_with_current(ovsdb_global_db):
    desired_state = {
        OvsDB.KEY: {
            OvsDB.EXTERNAL_IDS: {
                "opt1": None,
                "opt2": "value2new",
            },
            OvsDB.OTHER_CONFIG: {
                "flow-restore-wait": None,
                "tc-policy": "skip_hw",
            },
        }
    }
    libnmstate.apply(desired_state)

    current = libnmstate.show()[OvsDB.KEY]

    assert "opt1" not in current[OvsDB.EXTERNAL_IDS]
    assert current[OvsDB.EXTERNAL_IDS]["opt2"] == "value2new"
    assert "flow-restore-wait" not in current[OvsDB.OTHER_CONFIG]
    assert current[OvsDB.OTHER_CONFIG]["tc-policy"] == "skip_hw"


def test_ovsdb_global_preserve_not_mentioned(ovsdb_global_db):
    desired_state = {
        OvsDB.KEY: {
            OvsDB.OTHER_CONFIG: {
                "flow-restore-wait": None,
                "tc-policy": "skip_hw",
            },
        }
    }
    libnmstate.apply(desired_state)

    current = libnmstate.show()[OvsDB.KEY]

    assert current[OvsDB.EXTERNAL_IDS]["opt1"] == "value1"
    assert current[OvsDB.EXTERNAL_IDS]["opt2"] == "value2"
    assert "flow-restore-wait" not in current[OvsDB.OTHER_CONFIG]
    assert current[OvsDB.OTHER_CONFIG]["tc-policy"] == "skip_hw"


def test_ovsdb_global_remove_all(ovsdb_global_db):
    desired_state = {OvsDB.KEY: {}}
    libnmstate.apply(desired_state)

    current = libnmstate.show()[OvsDB.KEY]

    assert not current[OvsDB.EXTERNAL_IDS]


def test_ovsdb_global_remove_all_external_ids(ovsdb_global_db):
    desired_state = {OvsDB.KEY: {OvsDB.EXTERNAL_IDS: {}}}
    libnmstate.apply(desired_state)

    current = libnmstate.show()[OvsDB.KEY]

    assert not current[OvsDB.EXTERNAL_IDS]
    assert current[OvsDB.OTHER_CONFIG]["flow-restore-wait"] == "true"


def test_ovsdb_global_remove_all_other_config(ovsdb_global_db):
    desired_state = {OvsDB.KEY: {OvsDB.OTHER_CONFIG: {}}}
    libnmstate.apply(desired_state)

    current = libnmstate.show()[OvsDB.KEY]

    assert not current[OvsDB.OTHER_CONFIG]
    assert current[OvsDB.EXTERNAL_IDS]["opt1"] == "value1"
    assert current[OvsDB.EXTERNAL_IDS]["opt2"] == "value2"


def test_change_ovs_intenral_iface_ext_id_with_br_port_not_mentioned(
    bridge_with_ports,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
            },
            {
                Interface.NAME: PORT1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                OvsDB.OVS_DB_SUBTREE: {
                    OvsDB.EXTERNAL_IDS: {"foo": "abc", "bak": 1}
                },
            },
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_move_ovs_system_interface_to_bond(bridge_with_ports):
    with bond_interface(BOND1, ["eth1"], create=False) as desired_state:
        desired_state[Interface.KEY].append(
            {
                Interface.NAME: BRIDGE1,
                OVSBridge.CONFIG_SUBTREE: {
                    OVSBridge.PORT_SUBTREE: [
                        {
                            OVSBridge.Port.NAME: PORT1,
                        }
                    ]
                },
            }
        )
        libnmstate.apply(desired_state)


@pytest.mark.skipif(is_k8s(), reason="K8S does not support genconf")
def test_genconf_ovsdb_iface_external_ids(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: BRIDGE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                OVSBridge.CONFIG_SUBTREE: {
                    OVSBridge.PORT_SUBTREE: [
                        {
                            OVSBridge.Port.NAME: PORT1,
                        },
                        {
                            OVSBridge.Port.NAME: "eth1",
                        },
                    ]
                },
                OvsDB.OVS_DB_SUBTREE: {
                    OvsDB.EXTERNAL_IDS: {"foo": "abe", "bak": 3}
                },
            },
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                OvsDB.OVS_DB_SUBTREE: {
                    OvsDB.EXTERNAL_IDS: {"foo": "abd", "bak": 2}
                },
            },
            {
                Interface.NAME: PORT1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                OvsDB.OVS_DB_SUBTREE: {
                    OvsDB.EXTERNAL_IDS: {"foo": "abc", "bak": 1}
                },
            },
        ]
    }
    with gen_conf_apply(desired_state):
        assertlib.assert_state_match(desired_state)


def test_add_port_to_ovs_br_with_controller_property(
    ovs_bridge1_with_internal_port_same_name, eth2_up
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth2",
                    Interface.STATE: InterfaceState.UP,
                    Interface.CONTROLLER: BRIDGE1,
                }
            ]
        }
    )
    current_state = libnmstate.show()
    br_iface = None
    # The show_only() does not works well with ovs same name topology, hence
    # we use our own code.
    for iface in current_state[Interface.KEY]:
        if (
            iface[Interface.NAME] == BRIDGE1
            and iface[Interface.TYPE] == InterfaceType.OVS_BRIDGE
        ):
            br_iface = iface
            break
    br_ports = br_iface[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE]
    assert br_iface[Interface.NAME] == BRIDGE1
    assert len(br_ports) == 2
    assert br_ports[0][OVSBridge.Port.NAME] == BRIDGE1
    assert br_ports[1][OVSBridge.Port.NAME] == "eth2"


def test_move_ovs_sys_iface_to_linux_bridge(bridge_with_ports):
    bridge_config = {
        LinuxBridge.OPTIONS_SUBTREE: {
            LinuxBridge.STP_SUBTREE: {
                LinuxBridge.STP.ENABLED: False,
            },
        },
        LinuxBridge.PORT_SUBTREE: [
            {
                LinuxBridge.Port.NAME: "eth1",
            }
        ],
    }
    with linux_bridge("test-linux-br0", bridge_config) as state:
        assertlib.assert_state_match(state)


def test_ovs_vlan_access_mode_with_tag_0():
    bridge = Bridge(BRIDGE1)
    bridge.add_internal_port(PORT1, ipv4_state={InterfaceIPv4.ENABLED: False})
    bridge.set_port_option(
        PORT1,
        {
            OVSBridge.Port.NAME: PORT1,
            OVSBridge.Port.VLAN_SUBTREE: {
                OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.ACCESS,
                OVSBridge.Port.Vlan.TAG: 0,
            },
        },
    )
    with bridge.create() as state:
        assertlib.assert_state_match(state)

    assertlib.assert_absent(BRIDGE1)
    assertlib.assert_absent(PORT1)


@pytest.fixture
def cleanup_ovs_bridge():
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BRIDGE0,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ]
        }
    )


@pytest.mark.parametrize(
    "bond_mode",
    [
        OVSBridge.Port.LinkAggregation.Mode.ACTIVE_BACKUP,
        OVSBridge.Port.LinkAggregation.Mode.BALANCE_SLB,
        OVSBridge.Port.LinkAggregation.Mode.BALANCE_TCP,
        OVSBridge.Port.LinkAggregation.Mode.LACP,
    ],
    ids=["active-backup", "balance-slb", "balance-tcp", "lacp"],
)
def test_crate_ovs_bond(cleanup_ovs_bridge, eth1_up, eth2_up, bond_mode):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs0
            - name: bond0
              link-aggregation:
                mode: {bond_mode}
                port:
                - name: eth1
                - name: eth2
            """.format(
            bond_mode=bond_mode
        ),
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.fixture
def ovs_service_off():
    with disable_service("openvswitch"):
        yield


def test_global_ovsdb_with_ovs_service_off(ovs_service_off):
    libnmstate.apply({OvsDB.KEY: {}})


@pytest.fixture
def ovs_br_with_4_dummy_ports_ovs_bond():
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs-bond0
              link-aggregation:
                mode: balance-slb
                port:
                - name: dummy4
                - name: dummy1
                - name: dummy3
                - name: dummy2
        - name: dummy1
          type: dummy
          state: up
        - name: dummy2
          type: dummy
          state: up
        - name: dummy3
          type: dummy
          state: up
        - name: dummy4
          type: dummy
          state: up
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    yield
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: absent
        - name: dummy1
          type: dummy
          state: absent
        - name: dummy2
          type: dummy
          state: absent
        - name: dummy3
          type: dummy
          state: absent
        - name: dummy4
          type: dummy
          state: absent
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)


def test_ovs_detach_2_ports_from_4_ports_ovs_bond(
    ovs_br_with_4_dummy_ports_ovs_bond,
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs-bond0
              link-aggregation:
                mode: balance-slb
                port:
                - name: dummy2
                - name: dummy4
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


# OpenStack use case
@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 41,
    reason="OVS interface level other_config is not supported in NM 1.40-",
)
def test_ovs_bond_other_config_and_remove(
    cleanup_ovs_bridge, eth1_up, eth2_up
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs0
            - name: bond0
              link-aggregation:
                mode: balance-slb
                port:
                - name: eth1
                - name: eth2
                ovs-db:
                  external_ids:
                    test_str: foo1
                    test_num: 100
                  other_config:
                    bond-miimon-interval: 100
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs0
            - name: bond0
              link-aggregation:
                mode: balance-slb
                port:
                - name: eth1
                - name: eth2
                ovs-db: {}
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


# OpenStack use case
@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 41,
    reason="OVS interface level other_config is not supported in NM 1.40-",
)
def test_ovs_bridge_other_config_and_remove(
    cleanup_ovs_bridge, eth1_up, eth2_up
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          ovs-db:
            other_config:
              in-band-queue: 12
          bridge:
            port:
            - name: ovs0
            - name: bond0
              link-aggregation:
                mode: balance-slb
                port:
                - name: eth1
                - name: eth2
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br0
          type: ovs-bridge
          state: up
          ovs-db: {}
          bridge:
            port:
            - name: ovs0
            - name: bond0
              link-aggregation:
                mode: balance-slb
                port:
                - name: eth1
                - name: eth2
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


# OpenStack use case
@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 41,
    reason="OVS interface level other_config is not supported in NM 1.40-",
)
def test_ovs_sys_iface_other_config_and_remove(
    cleanup_ovs_bridge, eth1_up, eth2_up
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ovs-db:
            other_config:
              emc-insert-inv-prob: 90
        - name: br0
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs0
            - name: eth1
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)

    desired_state = yaml.load(
        """---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ovs-db: {}
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


@pytest.fixture
def ovs_bridge_with_auto_create_internal_iface():
    with Bridge(BRIDGE1).create():
        yield


def test_ovs_new_internal_iface_to_bridge_with_auto_create_iface(
    ovs_bridge_with_auto_create_internal_iface,
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br1
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: new_ovs0
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


def test_ovs_replace_internal_iface_to_bridge_with_auto_create_iface(
    ovs_bridge_with_auto_create_internal_iface,
):
    desired_state = yaml.load(
        """---
        interfaces:
        - name: br1
          type: ovs-interface
          state: absent
        - name: br1
          type: ovs-bridge
          state: up
          bridge:
            port:
            - name: ovs0
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


# OVS netdev datapath will use TUN interface for OVS internal interface
@pytest.mark.tier1
@pytest.mark.skipif(
    nm_minor_version() < 38,
    reason="OVS TUN interface was not supported in NM 1.38-",
)
def test_netdev_data_path(eth1_up):
    bridge = Bridge(BRIDGE1)
    bridge.add_system_port("eth1")
    bridge.set_options({OVSBridge.Options.DATAPATH: "netdev"})
    bridge.add_internal_port(
        PORT1,
        ipv4_state={
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.0.2.1",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        },
    )
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


@pytest.mark.tier1
def test_allow_extra_ovs_patch_ports(ovs_bridge_with_patch_ports):
    bridge = Bridge(BRIDGE1)
    bridge.add_system_port("eth1")
    desired_state = bridge.state
    desired_state[Interface.KEY][0][OVSBridge.CONFIG_SUBTREE][
        OVSBridge.ALLOW_EXTRA_PATCH_PORTS
    ] = True
    libnmstate.apply(desired_state)

    patch1_state = statelib.show_only((PATCH1,))

    assert patch1_state[Interface.KEY][0][Interface.CONTROLLER] == BRIDGE1
