# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Hsr

from .testlib import assertlib
from .testlib.hsrlib import hsr_interface
from .testlib.ifacelib import get_mac_address


ETH1 = "eth1"
ETH2 = "eth2"
HSR0 = "hsr0"


@pytest.fixture
def hsr0_with_eths(eth1_up, eth2_up):
    eth1 = eth1_up[Interface.KEY][0][Interface.NAME]
    eth2 = eth2_up[Interface.KEY][0][Interface.NAME]

    with hsr_interface(HSR0, eth1, eth2) as state:
        yield state


@pytest.mark.tier1
def test_add_hsr_and_remove(eth1_up, eth2_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: HSR0,
                Interface.TYPE: InterfaceType.HSR,
                Interface.STATE: InterfaceState.UP,
                Hsr.CONFIG_SUBTREE: {
                    Hsr.PORT1: ETH1,
                    Hsr.PORT2: ETH2,
                    Hsr.MULTICAST_SPEC: 40,
                    Hsr.PROTOCOL: "prp",
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


# https://issues.redhat.com/browse/RHEL-100758
@pytest.mark.tier1
def test_hsr_mac_address_sync(hsr0_with_eths):
    hsr_mac = get_mac_address("hsr0")
    eth1_mac = get_mac_address("eth1")
    eth2_mac = get_mac_address("eth2")

    assert hsr_mac is not None
    assert hsr_mac == eth1_mac
    assert hsr_mac == eth2_mac
