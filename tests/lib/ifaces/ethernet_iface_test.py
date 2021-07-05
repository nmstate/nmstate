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

import pytest
from copy import deepcopy

from libnmstate.error import NmstateValueError
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.ifaces.ethernet import EthernetIface

MAC_ADDRESS1 = "12:34:56:78:90:AB"
FOO_IFACE_NAME = "foo"


class TestEthernetIface:
    def test_merge_speed_duplex_autoneg_true(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: True,
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
                Ethernet.AUTO_NEGOTIATION: True,
            },
            Interface.MAC: MAC_ADDRESS1,
        }
        assert des_iface.auto_negotiation

    def test_merge_speed_duplex_autoneg_false(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: True,
                Ethernet.SPEED: 1000,
                Ethernet.DUPLEX: Ethernet.FULL_DUPLEX,
            },
            Interface.MAC: MAC_ADDRESS1,
        }
        des_iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: False,
            },
        }

        cur_iface = EthernetIface(iface_info)
        des_iface = EthernetIface(des_iface_info)

        des_iface.merge(cur_iface)

        assert des_iface.to_dict() == {
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
        assert des_iface.auto_negotiation is False
        assert des_iface.speed == 1000
        assert des_iface.duplex == Ethernet.FULL_DUPLEX

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
        iface.mark_as_desired()
        assert iface.state_for_verify() == expected_iface_info

    def test_valid_ethernet_with_autoneg(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {Ethernet.AUTO_NEGOTIATION: True},
        }

        iface = EthernetIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    def test_valid_ethernet_without_autoneg(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: False,
                Ethernet.SPEED: 1000,
                Ethernet.DUPLEX: Ethernet.FULL_DUPLEX,
            },
        }

        iface = EthernetIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    def test_invalid_ethernet_speed(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: False,
                Ethernet.SPEED: -1,
                Ethernet.DUPLEX: Ethernet.FULL_DUPLEX,
            },
        }

        iface = EthernetIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_invalid_ethernet_duplex(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.AUTO_NEGOTIATION: False,
                Ethernet.SPEED: 1000,
                Ethernet.DUPLEX: "wrongduplex",
            },
        }

        iface = EthernetIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    @pytest.mark.parametrize("valid_values", [0, 150, 256])
    def test_valid_with_sriov_total_vfs(self, valid_values):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: valid_values
                },
            },
        }
        iface = EthernetIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    @pytest.mark.parametrize("invalid_values", [-50, -1])
    def test_over_maximum_total_vfs_is_invalid(self, invalid_values):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: invalid_values
                },
            },
        }
        iface = EthernetIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    @pytest.mark.parametrize("vf_id", [-50, -1])
    def test_invalid_vf_ids(self, vf_id):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: 2,
                    Ethernet.SRIOV.VFS_SUBTREE: [
                        {Ethernet.SRIOV.VFS.ID: vf_id}
                    ],
                },
            },
        }
        iface = EthernetIface(iface_info)

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    @pytest.mark.parametrize("vf_id", [0, 1, 20])
    def test_valid_vf_ids(self, vf_id):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: 2,
                    Ethernet.SRIOV.VFS_SUBTREE: [
                        {Ethernet.SRIOV.VFS.ID: vf_id},
                    ],
                },
            },
        }
        iface = EthernetIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    def test_sriov_with_empty_vf_config_is_valid(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: 1,
                    Ethernet.SRIOV.VFS_SUBTREE: [],
                },
            },
        }
        iface = EthernetIface(iface_info)
        iface.pre_edit_validation_and_cleanup()

    def test_sriov_vf_config_is_valid(self):
        iface_info = {
            Interface.NAME: FOO_IFACE_NAME,
            Interface.TYPE: InterfaceType.ETHERNET,
            Ethernet.CONFIG_SUBTREE: {
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: 1,
                    Ethernet.SRIOV.VFS_SUBTREE: [
                        {
                            Ethernet.SRIOV.VFS.ID: 1,
                            Ethernet.SRIOV.VFS.MAC_ADDRESS: MAC_ADDRESS1,
                            Ethernet.SRIOV.VFS.SPOOF_CHECK: True,
                            Ethernet.SRIOV.VFS.TRUST: False,
                            Ethernet.SRIOV.VFS.MIN_TX_RATE: 1000,
                            Ethernet.SRIOV.VFS.MAX_TX_RATE: 2000,
                        }
                    ],
                },
            },
        }
        iface = EthernetIface(iface_info)
        iface.pre_edit_validation_and_cleanup()
