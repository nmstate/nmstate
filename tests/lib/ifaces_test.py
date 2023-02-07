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
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Ethernet
from libnmstate.schema import LinuxBridge
from libnmstate.schema import VLAN
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.ifaces import Ifaces
from libnmstate.ifaces.ifaces import BaseIface
from libnmstate.ifaces.ifaces import OvsBridgeIface
from libnmstate.state import state_match

from .testlib.bridgelib import LINUX_BRIDGE_IFACE_NAME
from .testlib.bridgelib import PORT1_IFACE_NAME
from .testlib.bridgelib import PORT2_IFACE_NAME
from .testlib.bridgelib import gen_bridge_iface_info
from .testlib.constants import MAC_ADDRESS1
from .testlib.constants import MAC_ADDRESS2
from .testlib.ifacelib import gen_foo_iface_info_static_ip
from .testlib.ifacelib import gen_foo_iface_info
from .testlib.ovslib import OVS_BRIDGE_IFACE_NAME
from .testlib.ovslib import OVS_IFACE_NAME
from .testlib.ovslib import gen_ovs_bridge_info

FOO1_IFACE_NAME = "foo1"
FOO2_IFACE_NAME = "foo2"
FOO3_IFACE_NAME = "foo3"
FOO4_IFACE_NAME = "foo4"
PARENT_IFACE_NAME = "parent"
CHILD_IFACE_NAME = "child"


class TestIfaces:
    def _gen_iface_infos(self):
        iface1_info = gen_foo_iface_info_static_ip()
        iface1_info[Interface.NAME] = FOO1_IFACE_NAME
        iface2_info = gen_foo_iface_info_static_ip()
        iface2_info[Interface.NAME] = FOO2_IFACE_NAME
        return [iface1_info, iface2_info]

    def test_duplicate_interface_name(self):
        iface_infos = self._gen_iface_infos()
        iface_infos.append(deepcopy(iface_infos[0]))
        with pytest.raises(NmstateValueError):
            Ifaces(des_iface_infos=iface_infos, cur_iface_infos=[])

    def test_init_cur_iface_infos_only(self):
        ifaces = Ifaces(
            des_iface_infos=[], cur_iface_infos=self._gen_iface_infos()
        )

        for iface_info in self._gen_iface_infos():
            cur_iface = ifaces.get_cur_iface(
                iface_info[Interface.NAME], iface_info[Interface.TYPE]
            )
            assert cur_iface.to_dict() == iface_info

    def test_init_des_iface_infos_only(self):
        ifaces = Ifaces(
            cur_iface_infos=[], des_iface_infos=self._gen_iface_infos()
        )

        assert [
            i.original_desire_dict for i in ifaces.all_ifaces()
        ] == self._gen_iface_infos()

    def test_add_new_iface(self):
        cur_iface_infos = self._gen_iface_infos()
        new_iface_info = gen_foo_iface_info()
        new_iface_info[Interface.NAME] = FOO3_IFACE_NAME

        ifaces = Ifaces([new_iface_info], cur_iface_infos)
        new_iface = ifaces.all_kernel_ifaces[FOO3_IFACE_NAME]
        iface1 = ifaces.all_kernel_ifaces[FOO1_IFACE_NAME]
        iface2 = ifaces.all_kernel_ifaces[FOO2_IFACE_NAME]

        assert (
            len(list(ifaces.all_kernel_ifaces.keys()))
            == len(self._gen_iface_infos()) + 1
        )
        assert new_iface.is_desired
        assert not iface1.is_desired
        assert not iface2.is_desired

    def test_edit_existing_iface(self):
        cur_iface_infos = self._gen_iface_infos()
        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0][Interface.MAC] = MAC_ADDRESS1
        expected_iface_info = deepcopy(des_iface_infos[0])

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)
        edit_iface = ifaces.all_kernel_ifaces[
            des_iface_infos[0][Interface.NAME]
        ]

        assert state_match(expected_iface_info, edit_iface.to_dict())
        assert edit_iface.is_desired

    def test_mark_iface_as_absent(self):
        cur_iface_infos = self._gen_iface_infos()
        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0][Interface.STATE] = InterfaceState.ABSENT
        expected_iface_info = deepcopy(des_iface_infos[0])

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)
        edit_iface = ifaces.all_kernel_ifaces[
            des_iface_infos[0][Interface.NAME]
        ]

        assert state_match(expected_iface_info, edit_iface.to_dict())
        assert edit_iface.is_desired
        assert edit_iface.is_absent

    def test_validate_unknown_port(self):
        cur_iface_infos = self._gen_iface_infos()
        des_iface_info = gen_bridge_iface_info()

        with pytest.raises(NmstateValueError):
            Ifaces([des_iface_info], cur_iface_infos)

    def test_validate_overbooked_port(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_iface_info1 = gen_bridge_iface_info()
        des_iface_info2 = gen_bridge_iface_info()
        des_iface_info2[Interface.NAME] = "another_bridge"

        with pytest.raises(NmstateValueError):
            Ifaces([des_iface_info1, des_iface_info2], cur_iface_infos)

    def test_ignore_overbooked_port_for_undesired_iface(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_info1 = gen_bridge_iface_info()
        cur_iface_info2 = gen_bridge_iface_info()
        cur_iface_info2[Interface.NAME] = "another_bridge"
        cur_iface_infos.append(cur_iface_info1)
        cur_iface_infos.append(cur_iface_info2)
        des_iface_infos = self._gen_iface_infos()
        Ifaces(des_iface_infos, cur_iface_infos)

    def test_remove_unknown_interfaces(self):
        des_iface_infos = self._gen_iface_infos()
        cur_iface_info = {
            Interface.NAME: FOO3_IFACE_NAME,
            Interface.TYPE: InterfaceType.UNKNOWN,
            Interface.STATE: InterfaceState.UP,
        }

        ifaces = Ifaces(des_iface_infos, [cur_iface_info])
        assert cur_iface_info not in ifaces.all_ifaces()

    def test_mark_port_as_changed_if_controller_marked_as_absent(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_info = gen_bridge_iface_info()
        des_iface_info[Interface.STATE] = InterfaceState.ABSENT

        ifaces = Ifaces([des_iface_info], cur_iface_infos)

        port_iface1 = ifaces.all_kernel_ifaces[PORT1_IFACE_NAME]
        port_iface2 = ifaces.all_kernel_ifaces[PORT2_IFACE_NAME]
        controller_iface = ifaces.all_kernel_ifaces[LINUX_BRIDGE_IFACE_NAME]

        assert port_iface1.is_changed
        assert port_iface2.is_changed
        assert port_iface1.is_up
        assert port_iface2.is_up
        assert port_iface1.controller is None
        assert port_iface2.controller is None
        assert controller_iface.is_desired
        assert controller_iface.is_absent

    def test_mark_port_as_changed_when_controller_changed_port_list(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_info = gen_bridge_iface_info()
        des_iface_info[LinuxBridge.CONFIG_SUBTREE][
            LinuxBridge.PORT_SUBTREE
        ].pop()

        ifaces = Ifaces([des_iface_info], cur_iface_infos)

        port_iface1 = ifaces.all_kernel_ifaces[PORT1_IFACE_NAME]
        port_iface2 = ifaces.all_kernel_ifaces[PORT2_IFACE_NAME]
        controller_iface = ifaces.all_kernel_ifaces[LINUX_BRIDGE_IFACE_NAME]

        assert not port_iface1.is_changed
        assert port_iface2.is_changed
        assert port_iface1.is_up
        assert port_iface2.is_up
        assert port_iface1.controller == LINUX_BRIDGE_IFACE_NAME
        assert port_iface2.controller is None
        assert controller_iface.is_desired

    def test_mark_port_as_changed_when_a_port_to_new_controller(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_iface_info = gen_bridge_iface_info()

        ifaces = Ifaces([des_iface_info], cur_iface_infos)

        port_iface1 = ifaces.all_kernel_ifaces[PORT1_IFACE_NAME]
        port_iface2 = ifaces.all_kernel_ifaces[PORT2_IFACE_NAME]
        controller_iface = ifaces.all_kernel_ifaces[LINUX_BRIDGE_IFACE_NAME]

        assert port_iface1.is_changed
        assert port_iface2.is_changed
        assert port_iface1.is_up
        assert port_iface2.is_up
        assert port_iface1.controller == LINUX_BRIDGE_IFACE_NAME
        assert port_iface2.controller == LINUX_BRIDGE_IFACE_NAME
        assert controller_iface.is_desired

    def test_mark_port_as_changed_when_controller_changed_port_config(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_info = gen_bridge_iface_info()
        des_iface_info[LinuxBridge.CONFIG_SUBTREE][LinuxBridge.PORT_SUBTREE][
            0
        ][LinuxBridge.Port.STP_PATH_COST] += 1

        ifaces = Ifaces([des_iface_info], cur_iface_infos)

        port_iface1 = ifaces.all_kernel_ifaces[PORT1_IFACE_NAME]
        port_iface2 = ifaces.all_kernel_ifaces[PORT2_IFACE_NAME]
        controller_iface = ifaces.all_kernel_ifaces[LINUX_BRIDGE_IFACE_NAME]

        assert port_iface1.is_changed
        assert not port_iface2.is_changed
        assert port_iface1.is_up
        assert port_iface2.is_up
        assert port_iface1.controller == LINUX_BRIDGE_IFACE_NAME
        assert port_iface2.controller == LINUX_BRIDGE_IFACE_NAME
        assert controller_iface.is_desired

    def test_mark_child_as_absent_when_parent_is_marked_as_absent(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PARENT_IFACE_NAME
        child_iface_info = gen_foo_iface_info(iface_type=InterfaceType.VLAN)
        child_iface_info[Interface.NAME] = CHILD_IFACE_NAME
        child_iface_info[VLAN.CONFIG_SUBTREE] = {
            VLAN.ID: 101,
            VLAN.BASE_IFACE: PARENT_IFACE_NAME,
        }
        cur_iface_infos.append(child_iface_info)

        des_iface_info = gen_foo_iface_info()
        des_iface_info[Interface.NAME] = PARENT_IFACE_NAME
        des_iface_info[Interface.STATE] = InterfaceState.ABSENT

        ifaces = Ifaces([des_iface_info], cur_iface_infos)

        child_iface = ifaces.all_kernel_ifaces[CHILD_IFACE_NAME]
        parent_iface = ifaces.all_kernel_ifaces[PARENT_IFACE_NAME]
        other_iface = ifaces.all_kernel_ifaces[FOO2_IFACE_NAME]

        assert parent_iface.is_desired
        assert child_iface.is_changed
        assert not other_iface.is_changed
        assert parent_iface.is_absent
        assert child_iface.is_absent
        assert other_iface.is_up

    def test_mark_orphen_as_absent(self):
        """
        When OVS internal interface been removed from OVS bridge port list,
        the orphen interface should be marked as absent.
        """
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos.append(gen_ovs_bridge_info())
        child_iface_info = gen_foo_iface_info(
            iface_type=InterfaceType.OVS_INTERFACE
        )
        child_iface_info[Interface.NAME] = OVS_IFACE_NAME
        cur_iface_infos.append(child_iface_info)

        des_ovs_bridge_info = gen_ovs_bridge_info()
        ovs_bridge_iface = OvsBridgeIface(des_ovs_bridge_info, True)
        ovs_bridge_iface.remove_port(OVS_IFACE_NAME)
        des_iface_info = ovs_bridge_iface.to_dict()

        ifaces = Ifaces([des_iface_info], cur_iface_infos)

        ovs_iface = ifaces.all_kernel_ifaces[OVS_IFACE_NAME]
        bridge_iface = ifaces.get_iface(
            OVS_BRIDGE_IFACE_NAME, InterfaceType.OVS_BRIDGE
        )
        port1_iface = ifaces.all_kernel_ifaces[PORT1_IFACE_NAME]
        port2_iface = ifaces.all_kernel_ifaces[PORT2_IFACE_NAME]

        assert bridge_iface.is_desired
        assert ovs_iface.is_changed
        assert not port1_iface.is_changed
        assert not port2_iface.is_changed
        assert bridge_iface.is_up
        assert port1_iface.is_up
        assert port2_iface.is_up
        assert ovs_iface.is_absent

    def test_validate_unknown_parent(self):
        child_iface_info = gen_foo_iface_info(iface_type=InterfaceType.VLAN)
        child_iface_info[VLAN.CONFIG_SUBTREE] = {
            VLAN.ID: 101,
            VLAN.BASE_IFACE: PARENT_IFACE_NAME,
        }
        with pytest.raises(NmstateValueError):
            Ifaces([child_iface_info], [])

    def test_state_to_edit_with_empty_desire(self):
        cur_iface_infos = self._gen_iface_infos()
        ifaces = Ifaces([], cur_iface_infos)

        assert ifaces.state_to_edit == []

    def test_state_to_edit_with_desire(self):
        cur_iface_infos = self._gen_iface_infos()
        des_iface_infos = self._gen_iface_infos()
        ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        assert sorted(
            [i[Interface.NAME] for i in ifaces.state_to_edit]
        ) == sorted([FOO1_IFACE_NAME, FOO2_IFACE_NAME])

    def test_state_to_edit_with_changed_only(self):
        cur_iface_infos = self._gen_iface_infos()
        ifaces = Ifaces([], cur_iface_infos)

        for iface in ifaces.all_ifaces():
            iface.mark_as_changed()

        assert sorted(
            [i[Interface.NAME] for i in ifaces.state_to_edit]
        ) == sorted([FOO1_IFACE_NAME, FOO2_IFACE_NAME])

    def test_state_to_edit_with_ignored_iface(self):
        cur_iface_infos = self._gen_iface_infos()
        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0][Interface.STATE] = InterfaceState.IGNORE
        ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        assert sorted([i[Interface.NAME] for i in ifaces.state_to_edit]) == [
            FOO2_IFACE_NAME
        ]

    def test_state_to_edit_with_ignored_subordinate(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        des_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_iface_infos[1][Interface.STATE] = InterfaceState.IGNORE
        des_bridge_info = gen_bridge_iface_info()
        des_bridge_info[LinuxBridge.CONFIG_SUBTREE][
            LinuxBridge.PORT_SUBTREE
        ] = []
        des_iface_infos.append(des_bridge_info)

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        assert sorted(
            [i[Interface.NAME] for i in ifaces.state_to_edit]
        ) == sorted([LINUX_BRIDGE_IFACE_NAME, PORT1_IFACE_NAME])

    def test_verify_desire_iface_not_found_in_current(self):
        cur_iface_infos = self._gen_iface_infos()
        cur_iface_infos.pop()

        des_iface_infos = self._gen_iface_infos()
        des_ifaces = Ifaces(des_iface_infos, [])

        with pytest.raises(NmstateVerificationError):
            des_ifaces.verify(cur_iface_infos)

    def test_verify_desire_iface_matches(self):
        cur_iface_infos = self._gen_iface_infos()

        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0].pop(Interface.TYPE)
        des_ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        des_ifaces.verify(cur_iface_infos)

    def test_verify_desire_iface_not_match(self):
        cur_iface_infos = self._gen_iface_infos()

        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0][Interface.MAC] = MAC_ADDRESS1
        des_ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        with pytest.raises(NmstateVerificationError):
            des_ifaces.verify(cur_iface_infos)

    def test_verify_with_ignored_interface(self):
        cur_iface_infos = self._gen_iface_infos()
        des_iface_infos = self._gen_iface_infos()
        des_iface_infos[0][Interface.STATE] = InterfaceState.IGNORE
        des_iface_infos[0]["foo"] = "bar"
        ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        ifaces.verify(cur_iface_infos)

    def test_verify_with_ignored_subordinate(self):
        cur_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        des_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        des_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_iface_infos[1][Interface.STATE] = InterfaceState.IGNORE
        des_bridge_info = gen_bridge_iface_info()
        des_bridge_info[LinuxBridge.CONFIG_SUBTREE][
            LinuxBridge.PORT_SUBTREE
        ].pop()
        des_iface_infos.append(des_bridge_info)

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)
        ifaces.verify(cur_iface_infos)

    def test_copy_mac_from_permanent_mac_address(self):
        cur_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos[1][Interface.MAC] = MAC_ADDRESS1
        cur_iface_infos[1][
            BaseIface.PERMANENT_MAC_ADDRESS_METADATA
        ] = MAC_ADDRESS2
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        des_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        des_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_bridge_info = gen_bridge_iface_info()
        des_bridge_info[Interface.NAME] = LINUX_BRIDGE_IFACE_NAME
        des_bridge_info[Interface.COPY_MAC_FROM] = PORT2_IFACE_NAME
        des_iface_infos.append(des_bridge_info)

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)
        assert (
            ifaces.all_kernel_ifaces[LINUX_BRIDGE_IFACE_NAME].mac
            == MAC_ADDRESS2
        )

    def test_copy_mac_from(self):
        cur_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        cur_iface_infos[1][Interface.MAC] = MAC_ADDRESS1
        cur_iface_infos.append(gen_bridge_iface_info())
        des_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        des_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        des_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_bridge_info = gen_bridge_iface_info()
        des_bridge_info[Interface.NAME] = LINUX_BRIDGE_IFACE_NAME
        des_bridge_info[Interface.COPY_MAC_FROM] = PORT2_IFACE_NAME
        des_iface_infos.append(des_bridge_info)

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)
        assert (
            ifaces.all_kernel_ifaces[LINUX_BRIDGE_IFACE_NAME].mac
            == MAC_ADDRESS1
        )

    def test_cur_iface_intact(self):
        cur_iface_infos = [gen_foo_iface_info(), gen_foo_iface_info()]
        cur_iface_infos[0][Interface.NAME] = PORT1_IFACE_NAME
        cur_iface_infos[1][Interface.NAME] = PORT2_IFACE_NAME
        des_bridge_info = gen_bridge_iface_info()
        des_bridge_info[Interface.NAME] = LINUX_BRIDGE_IFACE_NAME
        des_iface_infos = [des_bridge_info]

        ifaces = Ifaces(des_iface_infos, cur_iface_infos)
        ifaces.gen_metadata()
        cur_port1 = ifaces.get_cur_iface(
            PORT1_IFACE_NAME, InterfaceType.ETHERNET
        )
        cur_port2 = ifaces.get_cur_iface(
            PORT2_IFACE_NAME, InterfaceType.ETHERNET
        )
        des_port1 = ifaces.get_iface(PORT1_IFACE_NAME, InterfaceType.ETHERNET)
        des_port2 = ifaces.get_iface(PORT2_IFACE_NAME, InterfaceType.ETHERNET)

        assert cur_port1.controller is None
        assert cur_port2.controller is None
        assert des_port1.controller == LINUX_BRIDGE_IFACE_NAME
        assert des_port2.controller == LINUX_BRIDGE_IFACE_NAME


class TestIfacesSriov:
    def test_ignore_vf_when_pf_is_down(self):
        des_iface_infos = [gen_foo_iface_info(InterfaceType.ETHERNET)]
        des_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME
        des_iface_infos[0][Interface.STATE] = InterfaceState.DOWN
        des_iface_infos[0][Ethernet.CONFIG_SUBTREE] = {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
        }
        ifaces = Ifaces(des_iface_infos, [])
        assert len(list(ifaces.all_ifaces())) == 1
        assert ifaces.get_iface(
            FOO1_IFACE_NAME, InterfaceType.ETHERNET
        ).is_desired

    def test_ignore_vf_when_pf_is_absent(self):
        des_iface_infos = [gen_foo_iface_info(InterfaceType.ETHERNET)]
        des_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME
        des_iface_infos[0][Interface.STATE] = InterfaceState.ABSENT
        des_iface_infos[0][Ethernet.CONFIG_SUBTREE] = {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
        }
        ifaces = Ifaces(des_iface_infos, [])
        assert len(list(ifaces.all_ifaces())) == 1
        assert ifaces.get_iface(
            FOO1_IFACE_NAME, InterfaceType.ETHERNET
        ).is_desired

    def test_vf_been_mark_as_absent_when_srio_total_vf_decreased(self):
        cur_iface_infos = [
            gen_foo_iface_info(InterfaceType.ETHERNET),
            gen_foo_iface_info(InterfaceType.ETHERNET),
            gen_foo_iface_info(InterfaceType.ETHERNET),
            gen_foo_iface_info(InterfaceType.ETHERNET),
        ]
        cur_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME
        cur_iface_infos[0][Ethernet.CONFIG_SUBTREE] = {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 3}
        }
        cur_iface_infos[1][Interface.NAME] = f"{FOO1_IFACE_NAME}v0"
        cur_iface_infos[2][Interface.NAME] = f"{FOO1_IFACE_NAME}v1"
        cur_iface_infos[3][Interface.NAME] = f"{FOO1_IFACE_NAME}v2"

        des_iface_infos = [gen_foo_iface_info(InterfaceType.ETHERNET)]
        des_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME
        des_iface_infos[0][Ethernet.CONFIG_SUBTREE] = {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}
        }
        ifaces = Ifaces(des_iface_infos, cur_iface_infos)

        absent_iface = ifaces.get_iface(
            f"{FOO1_IFACE_NAME}v2", InterfaceType.ETHERNET
        )
        assert absent_iface.is_desired
        assert absent_iface.is_absent

    def test_ignore_sriov_vfs_if_not_desired(self):
        pre_apply_cur_iface_infos = [
            gen_foo_iface_info(InterfaceType.ETHERNET),
            gen_foo_iface_info(InterfaceType.ETHERNET),
            gen_foo_iface_info(InterfaceType.ETHERNET),
            gen_foo_iface_info(InterfaceType.ETHERNET),
        ]
        pre_apply_cur_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME
        pre_apply_cur_iface_infos[0][Ethernet.CONFIG_SUBTREE] = {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 3}
        }
        pre_apply_cur_iface_infos[1][Interface.NAME] = f"{FOO1_IFACE_NAME}v0"
        pre_apply_cur_iface_infos[2][Interface.NAME] = f"{FOO1_IFACE_NAME}v1"
        pre_apply_cur_iface_infos[3][Interface.NAME] = f"{FOO1_IFACE_NAME}v2"

        des_iface_infos = [gen_foo_iface_info(InterfaceType.ETHERNET)]
        des_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME

        des_ifaces = Ifaces(des_iface_infos, pre_apply_cur_iface_infos)

        cur_iface_infos = [
            gen_foo_iface_info(InterfaceType.ETHERNET),
        ]
        cur_iface_infos[0][Interface.NAME] = FOO1_IFACE_NAME
        cur_iface_infos[0][Ethernet.CONFIG_SUBTREE] = {
            Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 0}
        }

        des_ifaces.verify(cur_iface_infos)
