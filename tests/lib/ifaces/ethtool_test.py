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

from libnmstate.schema import Ethtool

from libnmstate.ifaces.base_iface import BaseIface
from ..testlib.ifacelib import gen_foo_iface_info


class TestIfaceEthtool:
    def test_pause_canonicalize_remove_rx_tx(self):
        des_info = gen_foo_iface_info()
        des_info.update(
            {
                Ethtool.CONFIG_SUBTREE: {
                    Ethtool.Pause.CONFIG_SUBTREE: {
                        Ethtool.Pause.AUTO_NEGOTIATION: True,
                        Ethtool.Pause.RX: True,
                        Ethtool.Pause.TX: True,
                    }
                }
            }
        )
        iface = BaseIface(des_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

        assert iface.ethtool.pause.autoneg is True
        assert iface.ethtool.pause.rx is None
        assert iface.ethtool.pause.tx is None

    def test_pause_match_ignore_rx_tx(self):
        des_info = gen_foo_iface_info()
        des_info.update(
            {
                Ethtool.CONFIG_SUBTREE: {
                    Ethtool.Pause.CONFIG_SUBTREE: {
                        Ethtool.Pause.AUTO_NEGOTIATION: True,
                        Ethtool.Pause.RX: True,
                        Ethtool.Pause.TX: True,
                    }
                }
            }
        )
        cur_info = deepcopy(des_info)
        cur_info[Ethtool.CONFIG_SUBTREE][Ethtool.Pause.CONFIG_SUBTREE][
            Ethtool.Pause.RX
        ] = False
        cur_info[Ethtool.CONFIG_SUBTREE][Ethtool.Pause.CONFIG_SUBTREE][
            Ethtool.Pause.TX
        ] = False

        des_iface = BaseIface(des_info)
        cur_iface = BaseIface(cur_info)
        assert des_iface.match(cur_iface)

    @pytest.mark.parametrize(
        "ethtool_cli_alias",
        [
            ("rx", "rx-checksum"),
            ("rx-checksumming", "rx-checksum"),
            ("ufo", "tx-udp-fragmentation"),
            ("gso", "tx-generic-segmentation"),
            ("generic-segmentation-offload", "tx-generic-segmentation"),
            ("gro", "rx-gro"),
            ("generic-receive-offload", "rx-gro"),
            ("lro", "rx-lro"),
            ("large-receive-offload", "rx-lro"),
            ("rxvlan", "rx-vlan-hw-parse"),
            ("rx-vlan-offload", "rx-vlan-hw-parse"),
            ("txvlan", "tx-vlan-hw-insert"),
            ("tx-vlan-offload", "tx-vlan-hw-insert"),
            ("ntuple", "rx-ntuple-filter"),
            ("ntuple-filters", "rx-ntuple-filter"),
            ("rxhash", "rx-hashing"),
            ("receive-hashing", "rx-hashing"),
        ],
        ids=[
            "rx",
            "rx-checksumming",
            "ufo",
            "gso",
            "generic-segmentation-offload",
            "gro",
            "generic-receive-offload",
            "lro",
            "large-receive-offload",
            "rxvlan",
            "rx-vlan-offload",
            "txvlan",
            "tx-vlan-offload",
            "ntuple",
            "ntuple-filters",
            "rxhash",
            "receive-hashing",
        ],
    )
    def test_feature_canonicalize_expand_alias(self, ethtool_cli_alias):
        alias, kernel_name = ethtool_cli_alias
        des_info = gen_foo_iface_info()
        des_info.update(
            {
                Ethtool.CONFIG_SUBTREE: {
                    Ethtool.Feature.CONFIG_SUBTREE: {alias: True}
                }
            }
        )

        cur_info = gen_foo_iface_info()
        cur_info.update(
            {
                Ethtool.CONFIG_SUBTREE: {
                    Ethtool.Feature.CONFIG_SUBTREE: {kernel_name: True}
                }
            }
        )
        des_iface = BaseIface(des_info)
        cur_iface = BaseIface(cur_info)
        assert des_iface.state_for_verify() == cur_iface.state_for_verify()
