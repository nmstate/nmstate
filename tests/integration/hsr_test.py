# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Hsr

from .testlib import assertlib
from .testlib.cmdlib import exec_cmd
from .testlib.env import kernel_newer_than
from .testlib.env import nm_minor_version
from .testlib.hsrlib import hsr_interface
from .testlib.ifacelib import get_mac_address
from .testlib.veth import create_veth_pair

ETH1 = "eth1"
ETH2 = "eth2"
ETH3 = "eth3"
HSR0 = "hsr0"


@pytest.fixture(scope="module", autouse=True)
def regenerate_eth2_after_hsr(test_env_setup):
    """Regenerate eth2 veth pair after HSR tests to get a fresh MAC.

    nmstate copy_hsr_mac() sets cloned-mac-address on HSR PRP port
    NM profiles but does not clean it up on removal, leaving eth1
    and eth2 with identical MACs for the rest of the test session.
    """
    yield
    exec_cmd(["ip", "link", "del", ETH2])
    create_veth_pair(ETH2, f"{ETH2}.ep", "nmstate_test_ep")


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


# https://issues.redhat.com/browse/RHEL-100773
@pytest.mark.tier1
def test_hsr_update_protocol(hsr0_with_eths):
    # Break if the default protocol in fixture is changed,
    # since it may render this test otherwise useless.
    assert (
        "prp"
        == hsr0_with_eths[Interface.KEY][0][Hsr.CONFIG_SUBTREE][Hsr.PROTOCOL]
    )
    hsr0_with_eths[Interface.KEY][0][Hsr.CONFIG_SUBTREE][Hsr.PROTOCOL] = "hsr"
    libnmstate.apply(hsr0_with_eths)
    assertlib.assert_state_match(hsr0_with_eths)


# https://issues.redhat.com/browse/RHEL-100763
@pytest.mark.tier1
@pytest.mark.skipif(
    not kernel_newer_than(6, 19) or nm_minor_version() < 56,
    reason=(
        "HSR protocol version is only supported by NetworkManager 1.56+, "
        "and kernel exposes this attribute only since 6.19+"
    ),
)
@pytest.mark.parametrize("protocol", ("hsr", "hsr-2010", "hsr-2012"))
def test_add_hsr_with_protocol_version(eth1_up, eth2_up, protocol):
    with hsr_interface(HSR0, ETH1, ETH2, protocol=protocol) as state:
        # hsr-2010 maps to hsr for backwards compatibility, so we expect to see
        # only `hsr` protocol in the state.
        state[Interface.KEY][0][Hsr.CONFIG_SUBTREE][Hsr.PROTOCOL] = (
            "hsr" if "hsr-2010" == protocol else protocol
        )
        assertlib.assert_state(state)
    assertlib.assert_absent(HSR0)


# https://issues.redhat.com/browse/RHEL-100766
@pytest.mark.tier1
@pytest.mark.skipif(
    not kernel_newer_than(6, 19) or nm_minor_version() < 55,
    reason=(
        "HSR interlink is only supported by NetworkManager 1.55+, "
        "and kernel exposes this attribute only since 6.19+"
    ),
)
def test_add_hsr_with_interlink(eth1_up, eth2_up, eth3_up):
    with hsr_interface(
        HSR0, ETH1, ETH2, protocol="hsr", interlink=ETH3
    ) as state:
        assertlib.assert_state(state)
    assertlib.assert_absent(HSR0)
