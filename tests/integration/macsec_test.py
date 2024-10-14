# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import MacSec

from .testlib import assertlib
from .testlib.apply import apply_with_description
from .testlib.env import nm_minor_version

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
                    MacSec.BASE_IFACE: ETH1,
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
        apply_with_description(
            "Configure the macsec0 device with the macsec "
            "config: base interface eth1, set encript to true, set mka-cak to"
            " 50b71a8ef0bd5751ea76de6d6c98c03a, set mka-ckn to "
            "f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550"
            ", set port to 0, set validation to strict, set send-sci to true",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        apply_with_description("Delete the macsec0 device", desired_state)


@pytest.mark.tier1
def test_add_macsec_and_modify(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: MACSEC0,
                Interface.TYPE: InterfaceType.MACSEC,
                Interface.STATE: InterfaceState.UP,
                MacSec.CONFIG_SUBTREE: {
                    MacSec.BASE_IFACE: ETH1,
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
        apply_with_description(
            "Configure the macsec0 device with the macsec "
            "config: base interface eth1, set encript to true, set mka-cak to"
            " 50b71a8ef0bd5751ea76de6d6c98c03a, set mka-ckn to "
            "f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550"
            ", set port to 0, set validation to strict, set send-sci to true",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)
        desired_state[Interface.KEY][0][MacSec.CONFIG_SUBTREE][
            MacSec.MKA_CAK
        ] = "50b71a8ef0bd5751ea76deaaaaaaaaaa"
        apply_with_description(
            "Change the pre-shared CAK (Connectivity Association Key) for "
            "MACsec Key Agreement to 50b71a8ef0bd5751ea76deaaaaaaaaaa for "
            "macsec0 device",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        apply_with_description("Remove the macsec0 device", desired_state)


# https://issues.redhat.com/browse/RHEL-24337
@pytest.mark.xfail(
    nm_minor_version() < 46,
    reason="NetworkManager 1.46- does not support MacSec offload",
)
@pytest.mark.tier1
def test_macsec_offload(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: MACSEC0,
                Interface.TYPE: InterfaceType.MACSEC,
                Interface.STATE: InterfaceState.UP,
                MacSec.CONFIG_SUBTREE: {
                    MacSec.BASE_IFACE: ETH1,
                    MacSec.ENCRYPT: True,
                    MacSec.MKA_CAK: MKA_CAK,
                    MacSec.MKA_CKN: MKA_CKN,
                    MacSec.PORT: 0,
                    MacSec.VALIDATION: MacSec.VALIDATION_STRICT,
                    MacSec.SEND_SCI: True,
                    MacSec.OFFLOAD: MacSec.OFFLOAD_OFF,
                },
            }
        ]
    }
    try:
        apply_with_description(
            "Configure the macsec0 device with the macsec "
            "config: base interface eth1, set encript to true, set mka-cak "
            "to 50b71a8ef0bd5751ea76de6d6c98c03a, set mka-ckn to "
            "f2b4297d39da7330910a74abc0449feb45b5c0b9fc23df1430e1898fcf1c4550"
            ", set port to 0, set validation to strict, set send-sci to true, "
            "set the macsec offload to off",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        apply_with_description("Delete the macsec0 device", desired_state)
