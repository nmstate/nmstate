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
        br_iface = ifaces[OVS_BRIDGE_IFACE_NAME]
        br_iface.gen_metadata(ifaces)
        br_iface.pre_edit_validation_and_cleanup()
        port1_iface = ifaces[PORT1_IFACE_NAME]
        port2_iface = ifaces[PORT2_IFACE_NAME]

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

        ovs_iface = ifaces[OVS_IFACE_NAME]
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


class TestOvsInternalIface:
    def _gen_iface_info(self):
        return gen_foo_iface_info(iface_type=InterfaceType.OVS_INTERFACE)

    def test_is_virtual(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).is_virtual

    def test_need_parent(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).need_parent

    def test_can_have_ip_as_port(self):
        assert OvsInternalIface(gen_ovs_bridge_info()).can_have_ip_as_port

    # The 'parent' property is tested by `test_auto_create_ovs_interface`.
