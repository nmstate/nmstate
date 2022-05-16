#
# Copyright (c) 2020-2021 Red Hat, Inc.
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

from copy import deepcopy
from operator import itemgetter

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.ifaces.ovs import OvsBridgeIface
from libnmstate.ifaces.ovs import OvsInternalIface
from libnmstate.ifaces.ifaces import Ifaces
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import OVSInterface

from ..testlib.constants import PORT1_IFACE_NAME
from ..testlib.constants import PORT2_IFACE_NAME
from ..testlib.ifacelib import gen_foo_iface_info
from ..testlib.ovslib import OVS_BRIDGE_IFACE_NAME
from ..testlib.ovslib import OVS_IFACE_NAME
from ..testlib.ovslib import PORT_PORT_CONFIGS
from ..testlib.ovslib import gen_ovs_bridge_info


PORT_PORT_CONFIGS_VLAN_ACCESSS = [
    {
        OVSBridge.Port.NAME: PORT1_IFACE_NAME,
        OVSBridge.Port.VLAN_SUBTREE: {
            OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.ACCESS,
            OVSBridge.Port.Vlan.TAG: 101,
        },
    },
    {
        OVSBridge.Port.NAME: PORT2_IFACE_NAME,
        OVSBridge.Port.VLAN_SUBTREE: {
            OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.ACCESS,
            OVSBridge.Port.Vlan.TAG: 102,
        },
    },
]

BOND_IFACE_NAME = "bond0"

OVSBond = OVSBridge.Port.LinkAggregation

BOND_PORT_CONFIG = {
    OVSBridge.Port.NAME: BOND_IFACE_NAME,
    OVSBridge.Port.LINK_AGGREGATION_SUBTREE: {
        OVSBond.MODE: OVSBond.Mode.ACTIVE_BACKUP,
        OVSBond.PORT_SUBTREE: [
            {OVSBond.Port.NAME: PORT1_IFACE_NAME},
            {OVSBond.Port.NAME: PORT2_IFACE_NAME},
        ],
    },
}

PORT_IFACE_NAMES = sorted([s[OVSBridge.Port.NAME] for s in PORT_PORT_CONFIGS])


@pytest.fixture
def portless_ovs_bridge_state():
    return {
        Interface.NAME: "ovs-br0",
        Interface.STATE: InterfaceState.UP,
        Interface.TYPE: OVSBridge.TYPE,
        OVSBridge.CONFIG_SUBTREE: {OVSBridge.PORT_SUBTREE: []},
    }


@pytest.fixture
def ovs_bridge_state(portless_ovs_bridge_state):
    port = {OVSBridge.Port.NAME: "eth1", OVSBridge.Port.VLAN_SUBTREE: {}}
    ovs_bridge_state_config = portless_ovs_bridge_state[
        OVSBridge.CONFIG_SUBTREE
    ]
    ovs_bridge_state_config[OVSBridge.PORT_SUBTREE].append(port)
    return portless_ovs_bridge_state


class TestOvsBrigeIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.OVS_BRIDGE)
        iface_info[OVSBridge.CONFIG_SUBTREE] = {
            OVSBridge.PORT_SUBTREE: deepcopy(PORT_PORT_CONFIGS),
            OVSBridge.OPTIONS_SUBTREE: {},
        }
        return iface_info

    def _gen_iface_info_with_bond(self):
        iface_info = gen_ovs_bridge_info()
        iface_info[OVSBridge.CONFIG_SUBTREE] = {
            OVSBridge.PORT_SUBTREE: [
                deepcopy(BOND_PORT_CONFIG),
                {OVSBridge.Port.NAME: OVS_IFACE_NAME},
            ],
            OVSBridge.OPTIONS_SUBTREE: {},
        }
        return iface_info

    def test_is_controller(self):
        iface = OvsBridgeIface(gen_ovs_bridge_info(), True)

        assert iface.is_controller

    def test_is_virtual(self):
        iface = OvsBridgeIface(gen_ovs_bridge_info(), True)

        assert iface.is_virtual

    def test_ovs_bridge_sort_port(self):
        iface1_info = gen_ovs_bridge_info()
        iface2_info = gen_ovs_bridge_info()
        iface2_info[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE].reverse()

        iface1 = OvsBridgeIface(iface1_info, True)
        iface2 = OvsBridgeIface(iface2_info, True)

        assert iface1.state_for_verify() == iface2.state_for_verify()
        assert iface1.port == PORT_IFACE_NAMES
        assert iface2.port == PORT_IFACE_NAMES

    def test_ovs_bridge_sort_bond_port(self):
        iface1_info = self._gen_iface_info_with_bond()
        iface2_info = self._gen_iface_info_with_bond()
        bond_config = iface2_info[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ][0]
        bond_config[OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
            OVSBond.PORT_SUBTREE
        ].reverse()

        iface1 = OvsBridgeIface(iface1_info, True)
        iface2 = OvsBridgeIface(iface2_info, True)

        assert iface1.state_for_verify() == iface2.state_for_verify()
        assert sorted(iface1.port) == PORT_IFACE_NAMES
        assert sorted(iface2.port) == PORT_IFACE_NAMES

    def test_gen_metadata_save_bond_port_config_to_port_iface(self):
        br_iface_info = self._gen_iface_info_with_bond()
        port1_iface_info = gen_foo_iface_info()
        port1_iface_info[Interface.NAME] = PORT1_IFACE_NAME
        port2_iface_info = gen_foo_iface_info()
        port2_iface_info[Interface.NAME] = PORT2_IFACE_NAME
        ifaces = Ifaces(
            des_iface_infos=[
                br_iface_info,
                port1_iface_info,
                port2_iface_info,
            ],
            cur_iface_infos=[port1_iface_info, port2_iface_info],
        )
        br_iface = ifaces.get_iface(
            OVS_BRIDGE_IFACE_NAME, InterfaceType.OVS_BRIDGE
        )
        br_iface.gen_metadata(ifaces)
        br_iface.pre_edit_validation_and_cleanup()
        port1_iface = ifaces.all_kernel_ifaces[PORT1_IFACE_NAME]
        port2_iface = ifaces.all_kernel_ifaces[PORT2_IFACE_NAME]

        assert port1_iface.controller == OVS_BRIDGE_IFACE_NAME
        assert port2_iface.controller == OVS_BRIDGE_IFACE_NAME
        assert (
            port1_iface.to_dict()[OvsBridgeIface.BRPORT_OPTIONS_METADATA]
            == BOND_PORT_CONFIG
        )
        assert (
            port2_iface.to_dict()[OvsBridgeIface.BRPORT_OPTIONS_METADATA]
            == BOND_PORT_CONFIG
        )

    def test_auto_create_ovs_interface(self):
        iface_info = gen_ovs_bridge_info()
        port1_iface_info = gen_foo_iface_info()
        port1_iface_info[Interface.NAME] = PORT1_IFACE_NAME
        port2_iface_info = gen_foo_iface_info()
        port2_iface_info[Interface.NAME] = PORT2_IFACE_NAME
        ifaces = Ifaces(
            des_iface_infos=[iface_info, port1_iface_info, port2_iface_info],
            cur_iface_infos=[port1_iface_info, port2_iface_info],
        )

        ovs_iface = ifaces.all_kernel_ifaces[OVS_IFACE_NAME]
        assert ovs_iface.type == InterfaceType.OVS_INTERFACE
        assert ovs_iface.parent == OVS_BRIDGE_IFACE_NAME
        assert ovs_iface.is_virtual
        assert ovs_iface.controller == OVS_BRIDGE_IFACE_NAME

    def test_validate_ovs_bond_with_single_port(self):
        iface_info = self._gen_iface_info_with_bond()
        bond_config = iface_info[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ][0][OVSBridge.Port.LINK_AGGREGATION_SUBTREE]
        bond_config[OVSBond.PORT_SUBTREE].pop()

        iface = OvsBridgeIface(iface_info, True)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_remove_port_from_bridge_without_bond(self):
        iface = OvsBridgeIface(gen_ovs_bridge_info(), True)
        iface.remove_port(PORT1_IFACE_NAME)

        assert sorted(iface.port) == sorted([PORT2_IFACE_NAME, OVS_IFACE_NAME])
        assert iface.to_dict()[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] == (
            sorted(
                [
                    {OVSBridge.Port.NAME: PORT2_IFACE_NAME},
                    {OVSBridge.Port.NAME: OVS_IFACE_NAME},
                ],
                key=itemgetter(OVSBridge.Port.NAME),
            )
        )

    def test_remove_port_from_bridge_with_bond(self):
        iface = OvsBridgeIface(self._gen_iface_info_with_bond(), True)
        iface.remove_port(PORT1_IFACE_NAME)
        expected_port_config = deepcopy(BOND_PORT_CONFIG)
        expected_port_config[OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
            OVSBond.PORT_SUBTREE
        ].pop(0)

        assert sorted(iface.port) == sorted([PORT2_IFACE_NAME, OVS_IFACE_NAME])
        assert iface.to_dict()[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] == sorted(
            [{OVSBridge.Port.NAME: OVS_IFACE_NAME}, expected_port_config],
            key=itemgetter(OVSBridge.Port.NAME),
        )

    @pytest.mark.parametrize(
        "vlan_mode",
        argvalues=[
            OVSBridge.Port.Vlan.Mode.TRUNK,
            OVSBridge.Port.Vlan.Mode.ACCESS,
        ],
    )
    def test_vlan_port_modes(self, ovs_bridge_state, vlan_mode):
        valid_vlan_mode = self._generate_vlan_config(vlan_mode)
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(valid_vlan_mode)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        iface.pre_edit_validation_and_cleanup()

    def test_invalid_vlan_port_mode(self, ovs_bridge_state):
        invalid_vlan_mode = self._generate_vlan_config("fake-mode")
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_vlan_mode)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_access_port_accepted(self, ovs_bridge_state):
        vlan_access_port_state = self._generate_vlan_config(
            OVSBridge.Port.Vlan.Mode.ACCESS, access_tag=101
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(vlan_access_port_state)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        iface.pre_edit_validation_and_cleanup()

    def test_wrong_access_port_tag_mode(self, ovs_bridge_state):
        invalid_access_port_tag_mode = self._generate_vlan_config(
            OVSBridge.Port.Vlan.Mode.ACCESS, access_tag="holy-guacamole!"
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_access_port_tag_mode)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_wrong_access_tag_range(self, ovs_bridge_state):
        invalid_vlan_id_range = self._generate_vlan_config(
            OVSBridge.Port.Vlan.Mode.ACCESS, access_tag=48000
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_vlan_id_range)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    @pytest.mark.parametrize(
        "is_native_vlan", argvalues=[True, False], ids=["native", "not-native"]
    )
    def test_trunk_port_native_vlan(self, ovs_bridge_state, is_native_vlan):
        vlan_access_port_state = self._generate_vlan_config(
            OVSBridge.Port.Vlan.Mode.TRUNK,
            access_tag=101 if is_native_vlan else None,
            native_vlan=is_native_vlan,
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(vlan_access_port_state)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        iface.pre_edit_validation_and_cleanup()

    def test_trunk_ports(self, ovs_bridge_state):
        trunk_tags = self._generate_vlan_id_config(101, 102, 103)
        trunk_tags.append(self._generate_vlan_id_range_config(500, 1000))
        vlan_trunk_tags_port_state = self._generate_vlan_config(
            OVSBridge.Port.Vlan.Mode.TRUNK, trunk_tags=trunk_tags
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(vlan_trunk_tags_port_state)
        iface = OvsBridgeIface(ovs_bridge_state, True)

        iface.pre_edit_validation_and_cleanup()

    @staticmethod
    def _generate_vlan_config(
        vlan_mode, trunk_tags=None, access_tag=None, native_vlan=None
    ):
        vlan_state = {
            OVSBridge.Port.Vlan.MODE: vlan_mode,
            OVSBridge.Port.Vlan.TRUNK_TAGS: trunk_tags or [],
        }

        if access_tag:
            vlan_state[OVSBridge.Port.Vlan.TAG] = access_tag
        if native_vlan:
            enable_native = OVSBridge.Port.Vlan.ENABLE_NATIVE
            vlan_state[enable_native] = native_vlan

        return {OVSBridge.Port.VLAN_SUBTREE: vlan_state}

    def test_valid_link_aggregation_port(self):
        link_aggregation_port = {
            OVSBridge.Port.NAME: "bond",
            OVSBridge.Port.LINK_AGGREGATION_SUBTREE: {
                OVSBridge.Port.LinkAggregation.MODE: "bond-mode",
                OVSBridge.Port.LinkAggregation.PORT_SUBTREE: [
                    {OVSBridge.Port.LinkAggregation.Port.NAME: "iface1"},
                    {OVSBridge.Port.LinkAggregation.Port.NAME: "iface2"},
                ],
            },
        }
        iface_info = {
            Interface.NAME: "bridge",
            Interface.TYPE: InterfaceType.OVS_BRIDGE,
            OVSBridge.CONFIG_SUBTREE: {
                OVSBridge.PORT_SUBTREE: [link_aggregation_port]
            },
        }
        iface = OvsBridgeIface(iface_info, True)

        iface.pre_edit_validation_and_cleanup()

    @staticmethod
    def _generate_vlan_id_config(*vlan_ids):
        return [
            {OVSBridge.Port.Vlan.TrunkTags.ID: vlan_id} for vlan_id in vlan_ids
        ]

    @staticmethod
    def _generate_vlan_id_range_config(min_vlan_id, max_vlan_id):
        return {
            OVSBridge.Port.Vlan.TrunkTags.ID_RANGE: {
                OVSBridge.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan_id,
                OVSBridge.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan_id,
            }
        }


class TestOvsInternalIface:
    def _gen_iface_info(self):
        return gen_foo_iface_info(iface_type=InterfaceType.OVS_INTERFACE)

    def test_is_virtual(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).is_virtual

    def test_need_parent(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).need_parent

    def test_can_have_ip_as_port(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).can_have_ip_as_port

    def test_is_dpdk(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.DEVARGS: "000:18:00.2"
            },
        }
        iface = OvsInternalIface(iface_info)

        assert iface.is_dpdk

    def test_devargs(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.DEVARGS: "000:18:00.2"
            },
        }
        iface = OvsInternalIface(iface_info)

        assert iface.devargs == "000:18:00.2"

    def test_rx_queue(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.RX_QUEUE: 1000
            },
        }
        iface = OvsInternalIface(iface_info)

        assert iface.rx_queue == 1000

    def test_dpdk_config(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.DEVARGS: "000:18:00.2"
            },
        }
        iface = OvsInternalIface(iface_info)

        assert iface.dpdk_config == {OVSInterface.Dpdk.DEVARGS: "000:18:00.2"}

    def test_valid_ovs_interface_with_devargs(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.DEVARGS: "000:18:00.2"
            },
        }
        iface = OvsInternalIface(iface_info)

        iface.pre_edit_validation_and_cleanup()

    def test_valid_ovs_interface_with_rx_queue(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.RX_QUEUE: 1000
            },
        }
        iface = OvsInternalIface(iface_info)

        iface.pre_edit_validation_and_cleanup()

    def test_invalid_ovs_interface_with_devargs(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {
                OVSInterface.Dpdk.DEVARGS: 23232
            },
        }
        iface = OvsInternalIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_invalid_ovs_interface_with_rx_queue(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.DPDK_CONFIG_SUBTREE: {OVSInterface.Dpdk.RX_QUEUE: -1},
        }
        iface = OvsInternalIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_valid_ovs_interface_with_peer(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.PATCH_CONFIG_SUBTREE: {
                OVSInterface.Patch.PEER: "ovs1"
            },
        }
        iface = OvsInternalIface(iface_info)

        iface.pre_edit_validation_and_cleanup()

    def test_invalid_ovs_interface_with_peer(self):
        iface_info = {
            Interface.NAME: "ovs0",
            Interface.TYPE: InterfaceType.OVS_INTERFACE,
            OVSInterface.PATCH_CONFIG_SUBTREE: {
                OVSInterface.Patch.PEER: 233132
            },
        }
        iface = OvsInternalIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_valid_ovs_interface_without_peer(self):
        iface_info = self._gen_iface_info()
        iface = OvsInternalIface(iface_info)

        iface.pre_edit_validation_and_cleanup()

    # The 'parent' property is tested by `test_auto_create_ovs_interface`.
