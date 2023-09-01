# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import MacSec

from .testlib import assertlib


MKA_CAK = "50b71a8ef0bd5751ea76de6d6c98c03a"
MKA_CKN = "f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550"
MACSEC0 = "macsec0"
ETH1 = "eth1"


@pytest.mark.tier1
def test_add_macsec_and_remove(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: MACSEC0,
                Interface.TYPE: InterfaceType.MACSEC,
                Interface.STATE: InterfaceState.UP,
                MacSec.CONFIG_SUBTREE: {
                    MacSec.PARENT: ETH1,
                    MacSec.ENCRYPT: True,
                    MacSec.MKA_CAK: MKA_CAK,
                    MacSec.MKA_CKN: MKA_CKN,
                    MacSec.PORT: 0,
                    MacSec.VALIDATION: MacSec.VALIDATION_STRICT,
                    MacSec.SEND_SCI: True,
                },
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)


@pytest.mark.tier1
def test_add_macsec_and_modify(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: MACSEC0,
                Interface.TYPE: InterfaceType.MACSEC,
                Interface.STATE: InterfaceState.UP,
                MacSec.CONFIG_SUBTREE: {
                    MacSec.PARENT: ETH1,
                    MacSec.ENCRYPT: True,
                    MacSec.MKA_CAK: MKA_CAK,
                    MacSec.MKA_CKN: MKA_CKN,
                    MacSec.PORT: 0,
                    MacSec.VALIDATION: MacSec.VALIDATION_STRICT,
                    MacSec.SEND_SCI: True,
                },
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
        desired_state[Interface.KEY][0][MacSec.CONFIG_SUBTREE][
            MacSec.MKA_CAK
        ] = "50b71a8ef0bd5751ea76deaaaaaaaaaa"
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)
