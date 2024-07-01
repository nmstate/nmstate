# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Hsr

from .testlib import assertlib
from .testlib.apply import apply_with_description
from .testlib.env import is_el8
from .testlib.env import nm_minor_version


ETH1 = "eth1"
ETH2 = "eth2"
HSR0 = "hsr0"


@pytest.mark.skipif(
    nm_minor_version() < 45 or is_el8(),
    reason=("HSR is only supported by NetworkManager 1.45+ and RHEL 9+"),
)
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
        apply_with_description(
            "Configure the hsr interface hsr0, set the config port to eth1 "
            "and eth2, set the hsr multicast spec to 40, set the hsr "
            "protocol to prp",
            desired_state,
        )
        assertlib.assert_state_match(desired_state)
    finally:
        desired_state[Interface.KEY][0][
            Interface.STATE
        ] = InterfaceState.ABSENT
        apply_with_description("Delete the hsr interface hsr0", desired_state)
