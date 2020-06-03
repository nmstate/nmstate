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
from operator import itemgetter

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.schema import OVSBridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.ovs import OvsBridgeIface
from libnmstate.ifaces.ovs import OvsInternalIface
from libnmstate.ifaces.ifaces import Ifaces

from ..testlib.constants import SLAVE1_IFACE_NAME
from ..testlib.constants import SLAVE2_IFACE_NAME
from ..testlib.ifacelib import gen_foo_iface_info
from ..testlib.ovslib import OVS_BRIDGE_IFACE_NAME
from ..testlib.ovslib import OVS_IFACE_NAME
from ..testlib.ovslib import SLAVE_PORT_CONFIGS
from ..testlib.ovslib import gen_ovs_bridge_info


SLAVE_PORT_CONFIGS_VLAN_ACCESSS = [
    {
        OVSBridge.Port.NAME: SLAVE1_IFACE_NAME,
        OVSBridge.Port.VLAN_SUBTREE: {
            OVSBridge.Port.Vlan.MODE: OVSBridge.Port.Vlan.Mode.ACCESS,
            OVSBridge.Port.Vlan.TAG: 101,
        },
    },
    {
        OVSBridge.Port.NAME: SLAVE2_IFACE_NAME,
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
        OVSBond.SLAVES_SUBTREE: [
            {OVSBond.Slave.NAME: SLAVE1_IFACE_NAME},
            {OVSBond.Slave.NAME: SLAVE2_IFACE_NAME},
        ],
    },
}

SLAVE_IFACE_NAMES = sorted(
    [s[OVSBridge.Port.NAME] for s in SLAVE_PORT_CONFIGS]
)


class TestOvsBrigeIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.OVS_BRIDGE)
        iface_info[OVSBridge.CONFIG_SUBTREE] = {
            OVSBridge.PORT_SUBTREE: deepcopy(SLAVE_PORT_CONFIGS),
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

    def test_is_master(self):
        iface = OvsBridgeIface(gen_ovs_bridge_info())

        assert iface.is_master

    def test_is_virtual(self):
        iface = OvsBridgeIface(gen_ovs_bridge_info())

        assert iface.is_virtual

    def test_ovs_bridge_sort_slaves(self):
        iface1_info = gen_ovs_bridge_info()
        iface2_info = gen_ovs_bridge_info()
        iface2_info[OVSBridge.CONFIG_SUBTREE][OVSBridge.PORT_SUBTREE].reverse()

        iface1 = OvsBridgeIface(iface1_info)
        iface2 = OvsBridgeIface(iface2_info)

        assert iface1.state_for_verify() == iface2.state_for_verify()
        assert iface1.slaves == SLAVE_IFACE_NAMES
        assert iface2.slaves == SLAVE_IFACE_NAMES

    def test_ovs_bridge_sort_bond_slaves(self):
        iface1_info = self._gen_iface_info_with_bond()
        iface2_info = self._gen_iface_info_with_bond()
        bond_config = iface2_info[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ][0]
        bond_config[OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
            OVSBond.SLAVES_SUBTREE
        ].reverse()

        iface1 = OvsBridgeIface(iface1_info)
        iface2 = OvsBridgeIface(iface2_info)

        assert iface1.state_for_verify() == iface2.state_for_verify()
        assert sorted(iface1.slaves) == SLAVE_IFACE_NAMES
        assert sorted(iface2.slaves) == SLAVE_IFACE_NAMES

    def test_gen_metadata_save_bond_port_config_to_slave_iface(self):
        br_iface_info = self._gen_iface_info_with_bond()
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
            cur_iface_infos=[slave1_iface_info, slave2_iface_info],
        )
        br_iface = ifaces[OVS_BRIDGE_IFACE_NAME]
        br_iface.gen_metadata(ifaces)
        br_iface.pre_edit_validation_and_cleanup()
        slave1_iface = ifaces[SLAVE1_IFACE_NAME]
        slave2_iface = ifaces[SLAVE2_IFACE_NAME]

        assert slave1_iface.master == OVS_BRIDGE_IFACE_NAME
        assert slave2_iface.master == OVS_BRIDGE_IFACE_NAME
        assert (
            slave1_iface.to_dict()[OvsBridgeIface.BRPORT_OPTIONS_METADATA]
            == BOND_PORT_CONFIG
        )
        assert (
            slave2_iface.to_dict()[OvsBridgeIface.BRPORT_OPTIONS_METADATA]
            == BOND_PORT_CONFIG
        )

    def test_auto_create_ovs_interface(self):
        iface_info = gen_ovs_bridge_info()
        slave1_iface_info = gen_foo_iface_info()
        slave1_iface_info[Interface.NAME] = SLAVE1_IFACE_NAME
        slave2_iface_info = gen_foo_iface_info()
        slave2_iface_info[Interface.NAME] = SLAVE2_IFACE_NAME
        ifaces = Ifaces(
            des_iface_infos=[
                iface_info,
                slave1_iface_info,
                slave2_iface_info,
            ],
            cur_iface_infos=[slave1_iface_info, slave2_iface_info],
        )

        ovs_iface = ifaces[OVS_IFACE_NAME]
        assert ovs_iface.iface_type == InterfaceType.OVS_INTERFACE
        assert ovs_iface.parent == OVS_BRIDGE_IFACE_NAME
        assert ovs_iface.is_virtual
        assert ovs_iface.master == OVS_BRIDGE_IFACE_NAME

    def test_validate_ovs_bond_with_single_slave(self):
        iface_info = self._gen_iface_info_with_bond()
        bond_config = iface_info[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ][0][OVSBridge.Port.LINK_AGGREGATION_SUBTREE]
        bond_config[OVSBond.SLAVES_SUBTREE].pop()

        iface = OvsBridgeIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_remove_slave_from_bridge_without_bond(self):
        iface = OvsBridgeIface(gen_ovs_bridge_info())
        iface.remove_slave(SLAVE1_IFACE_NAME)

        assert sorted(iface.slaves) == sorted(
            [SLAVE2_IFACE_NAME, OVS_IFACE_NAME]
        )
        assert iface.to_dict()[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] == (
            sorted(
                [
                    {OVSBridge.Port.NAME: SLAVE2_IFACE_NAME},
                    {OVSBridge.Port.NAME: OVS_IFACE_NAME},
                ],
                key=itemgetter(OVSBridge.Port.NAME),
            )
        )

    def test_remove_slave_from_bridge_with_bond(self):
        iface = OvsBridgeIface(self._gen_iface_info_with_bond())
        iface.remove_slave(SLAVE1_IFACE_NAME)
        expected_port_config = deepcopy(BOND_PORT_CONFIG)
        expected_port_config[OVSBridge.Port.LINK_AGGREGATION_SUBTREE][
            OVSBond.SLAVES_SUBTREE
        ].pop(0)

        assert sorted(iface.slaves) == sorted(
            [SLAVE2_IFACE_NAME, OVS_IFACE_NAME]
        )
        assert iface.to_dict()[OVSBridge.CONFIG_SUBTREE][
            OVSBridge.PORT_SUBTREE
        ] == sorted(
            [{OVSBridge.Port.NAME: OVS_IFACE_NAME}, expected_port_config],
            key=itemgetter(OVSBridge.Port.NAME),
        )


class TestOvsInternalIface:
    def _gen_iface_info(self):
        return gen_foo_iface_info(iface_type=InterfaceType.OVS_INTERFACE)

    def test_is_virtual(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).is_virtual

    def test_need_parent(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).need_parent

    def test_can_have_ip_when_enslaved(self):
        assert OvsInternalIface(
            gen_ovs_bridge_info()
        ).can_have_ip_when_enslaved

    # The 'parent' property is tested by `test_auto_create_ovs_interface`.
