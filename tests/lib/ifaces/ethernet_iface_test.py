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

from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.ifaces.ethernet import EthernetIface

MAC_ADDRESS1 = "12:34:56:78:90:AB"
FOO_IFACE_NAME = "foo"


class TestEthernetIface:
    def test_merge_speed_duplex(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: False,
                Ethernet.SPEED: 1000,
                Ethernet.DUPLEX: Ethernet.FULL_DUPLEX,
            },
            Interface.MAC: MAC_ADDRESS1,
        }
        des_iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
        }

        cur_iface = EthernetIface(iface_info)
        des_iface = EthernetIface(des_iface_info)

        des_iface.merge(cur_iface)

        assert des_iface.to_dict() == {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: None,
                Ethernet.SPEED: None,
                Ethernet.DUPLEX: None,
            },
            Interface.MAC: MAC_ADDRESS1,
        }

    def test_mix_cases_of_vf_mac_address(self):
        mac_addr = "FF:EE:dd:CC:BB:aa"
        expected_mac_addr = mac_addr.upper()
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: 2,
                    Ethernet.SRIOV.VFS_SUBTREE: [
                        {
                            Ethernet.SRIOV.VFS.ID: 0,
                            Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
                            Ethernet.SRIOV.VFS.MAC_ADDRESS: mac_addr,
                            Ethernet.SRIOV.VFS.TRUST: False,
                        }
                    ],
                },
            },
        }
        expected_iface_info = deepcopy(iface_info)
        expected_iface_info[Ethernet.CONFIG_SUBTREE][Ethernet.SRIOV_SUBTREE][
            Ethernet.SRIOV.VFS_SUBTREE
        ][0][Ethernet.SRIOV.VFS.MAC_ADDRESS] = expected_mac_addr

        iface = EthernetIface(iface_info)
        assert iface.state_for_verify() == expected_iface_info
