# SPDX-License-Identifier: LGPL-2.1-or-later

import libnmstate
from libnmstate.schema import Ethtool
from libnmstate.schema import Interface

from ..testlib import cmdlib


def test_coalesce_rx_tx_no_verify(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Ethtool.CONFIG_SUBTREE: {
                        Ethtool.Coalesce.CONFIG_SUBTREE: {
                            Ethtool.Coalesce.ADAPTIVE_RX: True,
                            Ethtool.Coalesce.ADAPTIVE_TX: True,
                        }
                    },
                }
            ]
        },
        verify_change=False,
    )
    assert (
        cmdlib.exec_cmd(
            "nmcli -g ethtool.coalesce-adaptive-rx c show eth1".split()
        )[1].strip()
        == "1"
    )
    assert (
        cmdlib.exec_cmd(
            "nmcli -g ethtool.coalesce-adaptive-tx c show eth1".split()
        )[1].strip()
        == "1"
    )
