# SPDX-License-Identifier: LGPL-2.1-or-later

import os

import pytest

from libnmstate.schema import Bond
from libnmstate.schema import BondMode

from ..testlib import assertlib
from ..testlib import cmdlib
from ..testlib.bondlib import bond_interface
from ..testlib.env import nm_minor_version


BOND0 = "bondtest0"


def test_bond_all_zero_ad_actor_system():
    extra_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.LACP,
            Bond.OPTIONS_SUBTREE: {"ad_actor_system": "00:00:00:00:00:00"},
        }
    }
    with bond_interface(
        name=BOND0, port=[], extra_iface_state=extra_iface_state, create=True
    ):
        _, output, _ = cmdlib.exec_cmd(
            f"nmcli --fields bond.options c show {BOND0}".split(), check=True
        )
        assert "ad_actor_system" in output

    assertlib.assert_absent(BOND0)


@pytest.mark.skipif(
    nm_minor_version() <= 40 or os.environ.get("CI") == "true",
    reason="Bond SLB is only supported by NM 1.41 with patched kernel",
)
def test_bond_balance_slb():
    extra_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.XOR,
            Bond.OPTIONS_SUBTREE: {
                "xmit_hash_policy": "vlan+srcmac",
                "balance-slb": 1,
            },
        }
    }
    with bond_interface(
        name=BOND0, port=[], extra_iface_state=extra_iface_state, create=True
    ):
        _, output, _ = cmdlib.exec_cmd(
            f"nmcli --fields bond.options c show {BOND0}".split(), check=True
        )
        assert "balance-slb=1" in output
        extra_iface_state[Bond.CONFIG_SUBTREE][Bond.OPTIONS_SUBTREE][
            "balance-slb"
        ] = False
        with bond_interface(
            name=BOND0,
            port=[],
            extra_iface_state=extra_iface_state,
            create=True,
        ):
            _, output, _ = cmdlib.exec_cmd(
                f"nmcli --fields bond.options c show {BOND0}".split(),
                check=True,
            )
            assert "balance-slb=0" in output

    assertlib.assert_absent(BOND0)
