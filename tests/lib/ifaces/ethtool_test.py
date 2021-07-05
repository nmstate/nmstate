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

import pytest

from libnmstate.error import NmstateValueError
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

    def test_valid_ethtool(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: False,
                Ethtool.Pause.TX: True,
                Ethtool.Pause.RX: True,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

    def test_invalid_ethtool_with_interger_value(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: 1,
                Ethtool.Pause.TX: 0,
                Ethtool.Pause.RX: 0,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()

        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_valid_ethtool_feature(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Feature.CONFIG_SUBTREE: {"rx-all": False}
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

    def test_valid_ethtool_ring(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Ring.CONFIG_SUBTREE: {
                Ethtool.Ring.RX: 256,
                Ethtool.Ring.RX_JUMBO: 4096,
                Ethtool.Ring.RX_MINI: 256,
                Ethtool.Ring.TX: 256,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

    def test_invalid_ethtool_ring_out_of_range(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Ring.CONFIG_SUBTREE: {
                Ethtool.Ring.RX: -1,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_invalid_ethtool_ring_not_integer(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Ring.CONFIG_SUBTREE: {
                Ethtool.Ring.RX: False,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()

    def test_valid_ethtool_coalesce(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Coalesce.CONFIG_SUBTREE: {
                Ethtool.Coalesce.ADAPTIVE_RX: True,
                Ethtool.Coalesce.ADAPTIVE_TX: True,
                Ethtool.Coalesce.PKT_RATE_HIGH: 100,
                Ethtool.Coalesce.PKT_RATE_LOW: 100,
                Ethtool.Coalesce.RX_FRAMES: 100,
                Ethtool.Coalesce.RX_FRAMES_HIGH: 100,
                Ethtool.Coalesce.RX_FRAMES_IRQ: 100,
                Ethtool.Coalesce.RX_FRAMES_LOW: 100,
                Ethtool.Coalesce.RX_USECS: 100,
                Ethtool.Coalesce.RX_USECS_HIGH: 100,
                Ethtool.Coalesce.RX_USECS_IRQ: 100,
                Ethtool.Coalesce.RX_USECS_LOW: 100,
                Ethtool.Coalesce.SAMPLE_INTERVAL: 100,
                Ethtool.Coalesce.STATS_BLOCK_USECS: 100,
                Ethtool.Coalesce.TX_FRAMES: 100,
                Ethtool.Coalesce.TX_FRAMES_HIGH: 100,
                Ethtool.Coalesce.TX_FRAMES_IRQ: 100,
                Ethtool.Coalesce.TX_FRAMES_LOW: 100,
                Ethtool.Coalesce.TX_USECS: 100,
                Ethtool.Coalesce.TX_USECS_HIGH: 100,
                Ethtool.Coalesce.TX_USECS_IRQ: 100,
                Ethtool.Coalesce.TX_USECS_LOW: 100,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        iface.pre_edit_validation_and_cleanup()

    def test_invalid_ethtool_coalesce_invalid_value_type(self):
        iface_info = gen_foo_iface_info()
        iface_info[Ethtool.CONFIG_SUBTREE] = {
            Ethtool.Coalesce.CONFIG_SUBTREE: {
                Ethtool.Coalesce.ADAPTIVE_RX: 1,
                Ethtool.Coalesce.ADAPTIVE_TX: 0,
            }
        }
        iface = BaseIface(iface_info)
        iface.mark_as_desired()
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()
