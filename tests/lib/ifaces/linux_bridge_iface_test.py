#
# Copyright (c) 2020 Red Hat, Inc.
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

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge as LB

from libnmstate.ifaces.linux_bridge import LinuxBridgeIface
from libnmstate.ifaces.ifaces import Ifaces

from ..testlib.bridgelib import LINUX_BRIDGE_IFACE_NAME
from ..testlib.bridgelib import TEST_SLAVE_NAMES
from ..testlib.bridgelib import SLAVE1_IFACE_NAME
from ..testlib.bridgelib import SLAVE1_PORT_CONFIG
from ..testlib.bridgelib import SLAVE2_IFACE_NAME
from ..testlib.bridgelib import SLAVE2_PORT_CONFIG
from ..testlib.bridgelib import SLAVE2_VLAN_CONFIG_TRUNK
from ..testlib.bridgelib import TRUNK_TAGS_ID_RANGES
from ..testlib.bridgelib import gen_bridge_iface_info
from ..testlib.bridgelib import gen_bridge_iface_info_with_vlan_filter
from ..testlib.ifacelib import gen_foo_iface_info

Port = LB.Port
Vlan = LB.Port.Vlan


class TestLinuxBridgeIface:
    def test_linux_bridge_sort_slaves(self):
        iface_info1 = gen_bridge_iface_info()
        iface_info2 = gen_bridge_iface_info()
        iface_info2[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE].reverse()

        assert (
            LinuxBridgeIface(iface_info1).state_for_verify()
            == LinuxBridgeIface(iface_info2).state_for_verify()
        )

    def test_is_master(self):
        iface = LinuxBridgeIface(gen_bridge_iface_info())

        assert iface.is_master

    def test_is_virtual(self):
        iface = LinuxBridgeIface(gen_bridge_iface_info())

        assert iface.is_virtual

    def test_get_slaves(self):
        iface = LinuxBridgeIface(gen_bridge_iface_info())

        assert iface.slaves == TEST_SLAVE_NAMES

    def test_desire_port_name_full_merge_from_current(self):
        cur_iface_info = gen_bridge_iface_info()
        des_iface_info = gen_bridge_iface_info()
        des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = [
            {Port.NAME: SLAVE2_IFACE_NAME},
            {Port.NAME: SLAVE1_IFACE_NAME},
        ]
        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)

        des_iface.merge(cur_iface)
        des_iface.sort_slaves()
        cur_iface.sort_slaves()

        assert des_iface.to_dict() == gen_bridge_iface_info()

    def test_desire_port_name_only_merge_config_from_current(self):
        cur_iface_info = gen_bridge_iface_info()
        des_iface_info = gen_bridge_iface_info()
        expected_iface_info = gen_bridge_iface_info()
        expected_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = [
            deepcopy(SLAVE2_PORT_CONFIG)
        ]
        des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = [
            {Port.NAME: SLAVE2_IFACE_NAME},
        ]

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)

        assert des_iface.to_dict() == expected_iface_info

    def test_merged_with_desire_remove_all_ports(self):
        cur_iface_info = gen_bridge_iface_info()
        des_iface_info = gen_bridge_iface_info()
        expected_iface_info = gen_bridge_iface_info()
        expected_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = []
        des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = []

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)

        assert des_iface.to_dict() == expected_iface_info

    def test_merge_with_desired_ports_not_defined(self):
        cur_iface_info = gen_bridge_iface_info()
        des_iface_info = gen_bridge_iface_info()
        expected_iface_info = gen_bridge_iface_info()
        des_iface_info[LB.CONFIG_SUBTREE].pop(LB.PORT_SUBTREE)

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)

        assert des_iface.to_dict() == expected_iface_info

    def test_desire_port_name_partial_merge_from_current_with_vlan_filter(
        self,
    ):
        cur_iface_info = gen_bridge_iface_info_with_vlan_filter()
        des_iface_info = gen_bridge_iface_info_with_vlan_filter()
        expected_port_config = deepcopy(SLAVE2_PORT_CONFIG)
        expected_port_config[Port.VLAN_SUBTREE] = SLAVE2_VLAN_CONFIG_TRUNK
        expected_iface_info = gen_bridge_iface_info()
        expected_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = [
            expected_port_config
        ]
        des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = [
            {Port.NAME: SLAVE2_IFACE_NAME},
        ]

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)

        assert des_iface.to_dict() == expected_iface_info

    def test_fix_access_mode_with_enable_native(self):
        cur_iface_info = gen_bridge_iface_info_with_vlan_filter()
        des_iface_info = gen_bridge_iface_info_with_vlan_filter()
        expected_iface_info = gen_bridge_iface_info_with_vlan_filter()
        cur_vlan_conf = cur_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0][
            Port.VLAN_SUBTREE
        ]
        cur_vlan_conf[Vlan.ENABLE_NATIVE] = True
        cur_vlan_conf[Vlan.MODE] = Vlan.Mode.TRUNK

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)
        des_iface.pre_edit_validation_and_cleanup()

        assert des_iface.to_dict() == expected_iface_info

    def test_merge_fix_tag_with_trunk_disabled_native(self):
        cur_iface_info = gen_bridge_iface_info_with_vlan_filter()
        des_iface_info = gen_bridge_iface_info_with_vlan_filter()
        des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0][
            Port.VLAN_SUBTREE
        ] = {
            Vlan.ENABLE_NATIVE: False,
            Vlan.MODE: Vlan.Mode.TRUNK,
            Vlan.TRUNK_TAGS: [{Vlan.TrunkTags.ID: 101}],
        }
        expected_iface_info = deepcopy(des_iface_info)

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)
        des_iface.pre_edit_validation_and_cleanup()

        assert des_iface.to_dict() == expected_iface_info

    def test_remove_trunk_tag_if_access_mode(self):
        cur_iface_info = gen_bridge_iface_info_with_vlan_filter()
        des_iface_info = gen_bridge_iface_info_with_vlan_filter()
        des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][1][
            Port.VLAN_SUBTREE
        ] = {
            Vlan.MODE: Vlan.Mode.ACCESS,
        }
        expected_iface_info = gen_bridge_iface_info_with_vlan_filter()
        expected_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][1][
            Port.VLAN_SUBTREE
        ] = {Vlan.MODE: Vlan.Mode.ACCESS, Vlan.TAG: 105}

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)
        des_iface.merge(cur_iface)
        des_iface.pre_edit_validation_and_cleanup()

        assert des_iface.to_dict() == expected_iface_info

    def test_gen_metadata_save_port_config_to_slave_iface(self):
        br_iface_info = gen_bridge_iface_info()
        slave1_iface_info = gen_foo_iface_info()
        slave1_iface_info[Interface.NAME] = SLAVE1_IFACE_NAME
        slave2_iface_info = gen_foo_iface_info()
        slave2_iface_info[Interface.NAME] = SLAVE2_IFACE_NAME
        ifaces = Ifaces(
            des_iface_infos=[
                br_iface_info,
                slave1_iface_info,
                slave2_iface_info,
            ],
            cur_iface_infos=[],
        )
        br_iface = ifaces[LINUX_BRIDGE_IFACE_NAME]
        br_iface.gen_metadata(ifaces)
        br_iface.pre_edit_validation_and_cleanup()
        slave1_iface = ifaces[SLAVE1_IFACE_NAME]
        slave2_iface = ifaces[SLAVE2_IFACE_NAME]

        assert slave1_iface.master == LINUX_BRIDGE_IFACE_NAME
        assert slave2_iface.master == LINUX_BRIDGE_IFACE_NAME
        assert (
            slave1_iface.to_dict()[LinuxBridgeIface.BRPORT_OPTIONS_METADATA]
            == SLAVE1_PORT_CONFIG
        )
        assert (
            slave2_iface.to_dict()[LinuxBridgeIface.BRPORT_OPTIONS_METADATA]
            == SLAVE2_PORT_CONFIG
        )

    def test_gen_metadata_skip_on_absent_iface(self):
        br_iface_info = gen_bridge_iface_info()
        br_iface_info[Interface.STATE] = InterfaceState.ABSENT
        slave1_iface_info = gen_foo_iface_info()
        slave1_iface_info[Interface.NAME] = SLAVE1_IFACE_NAME
        slave2_iface_info = gen_foo_iface_info()
        slave2_iface_info[Interface.NAME] = SLAVE2_IFACE_NAME
        ifaces = Ifaces(
            des_iface_infos=[
                br_iface_info,
                slave1_iface_info,
                slave2_iface_info,
            ],
            cur_iface_infos=[],
        )
        br_iface = ifaces[LINUX_BRIDGE_IFACE_NAME]
        br_iface.gen_metadata(ifaces)
        br_iface.pre_edit_validation_and_cleanup()
        slave1_iface = ifaces[SLAVE1_IFACE_NAME]
        slave2_iface = ifaces[SLAVE2_IFACE_NAME]
        assert slave1_iface.master is None
        assert slave2_iface.master is None
        assert (
            LinuxBridgeIface.BRPORT_OPTIONS_METADATA
            not in slave1_iface.to_dict()
        )
        assert (
            LinuxBridgeIface.BRPORT_OPTIONS_METADATA
            not in slave2_iface.to_dict()
        )

    def test_state_for_verify_normalize_port_vlan(self):
        iface = LinuxBridgeIface(gen_bridge_iface_info())
        expected_iface_info = gen_bridge_iface_info()
        for port_config in expected_iface_info[LB.CONFIG_SUBTREE][
            LB.PORT_SUBTREE
        ]:
            port_config[Port.VLAN_SUBTREE] = {}

        assert iface.state_for_verify() == expected_iface_info

    def test_validate_access_port_with_trunk_tag(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        port_config = iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        port_config[Port.VLAN_SUBTREE][Vlan.TRUNK_TAGS] = [
            {Vlan.TrunkTags.ID: 101}
        ]

        iface = LinuxBridgeIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_trunk_port_without_trunk_tag(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        port_config = iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][1]
        port_config[Port.VLAN_SUBTREE].pop(Vlan.TRUNK_TAGS)

        iface = LinuxBridgeIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_trunk_mixing_id_and_id_range(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        port_config = iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][1]
        port_config[Port.VLAN_SUBTREE][Vlan.TRUNK_TAGS][0].update(
            TRUNK_TAGS_ID_RANGES[0]
        )

        iface = LinuxBridgeIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_trunk_id_range_missing_min_or_max(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        port_config = iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][1]
        port_config[Port.VLAN_SUBTREE][Vlan.TRUNK_TAGS][0] = {
            Vlan.TrunkTags.ID_RANGE: {Vlan.TrunkTags.MIN_RANGE: 400}
        }

        iface = LinuxBridgeIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

        port_config[Port.VLAN_SUBTREE][Vlan.TRUNK_TAGS][0] = {
            Vlan.TrunkTags.ID_RANGE: {Vlan.TrunkTags.MAX_RANGE: 400}
        }

        iface = LinuxBridgeIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_tag_in_access_mode_and_native_trunk(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        iface = LinuxBridgeIface(iface_info)

        iface.pre_edit_validation_and_cleanup()

    def test_validate_tag_in_non_native_trunk(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        port_conf = iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][1]
        port_conf[Port.VLAN_SUBTREE][Vlan.ENABLE_NATIVE] = False
        iface = LinuxBridgeIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_validate_enable_native_in_access_mode(self):
        iface_info = gen_bridge_iface_info_with_vlan_filter()
        port_conf = iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        port_conf[Port.VLAN_SUBTREE][Vlan.ENABLE_NATIVE] = True
        iface = LinuxBridgeIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_remove_slave(self):
        iface_info = gen_bridge_iface_info()
        expected_iface_info = gen_bridge_iface_info()
        expected_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] = [
            deepcopy(SLAVE1_PORT_CONFIG)
        ]

        iface = LinuxBridgeIface(iface_info)
        iface.remove_slave(SLAVE2_IFACE_NAME)

        assert iface.to_dict() == expected_iface_info

    def test_verify_when_vlantree_not_defined_in_desire(self):
        iface_info = gen_bridge_iface_info()
        expected_iface_info = gen_bridge_iface_info()
        for port_config in expected_iface_info[LB.CONFIG_SUBTREE][
            LB.PORT_SUBTREE
        ]:
            port_config[Port.VLAN_SUBTREE] = {}

        iface = LinuxBridgeIface(iface_info)

        assert iface.state_for_verify() == expected_iface_info

    def test_get_config_changed_slaves(self):
        des_iface_info = gen_bridge_iface_info()
        des_port_config = des_iface_info[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        des_port_config[Port.STP_PATH_COST] += 1
        cur_iface_info = gen_bridge_iface_info()

        des_iface = LinuxBridgeIface(des_iface_info)
        cur_iface = LinuxBridgeIface(cur_iface_info)

        assert des_iface.config_changed_slaves(cur_iface) == [
            SLAVE1_IFACE_NAME
        ]

    def test_skip_metadata_generation_when_is_absent(self):
        br_iface_info = gen_bridge_iface_info()
        br_iface_info[Interface.STATE] = InterfaceState.ABSENT
        slave1_iface_info = gen_foo_iface_info()
        slave1_iface_info[Interface.NAME] = SLAVE1_IFACE_NAME
        slave2_iface_info = gen_foo_iface_info()
        slave2_iface_info[Interface.NAME] = SLAVE2_IFACE_NAME
        ifaces = Ifaces(
            des_iface_infos=[
                br_iface_info,
                slave1_iface_info,
                slave2_iface_info,
            ],
            cur_iface_infos=[],
        )
        br_iface = ifaces[LINUX_BRIDGE_IFACE_NAME]
        br_iface.gen_metadata(ifaces)
        br_iface.pre_edit_validation_and_cleanup()
        slave1_iface = ifaces[SLAVE1_IFACE_NAME]
        slave2_iface = ifaces[SLAVE2_IFACE_NAME]

        assert slave1_iface.master is None
        assert slave2_iface.master is None
        assert (
            LinuxBridgeIface.BRPORT_OPTIONS_METADATA
            not in slave1_iface.to_dict()
        )
        assert (
            LinuxBridgeIface.BRPORT_OPTIONS_METADATA
            not in slave2_iface.to_dict()
        )
