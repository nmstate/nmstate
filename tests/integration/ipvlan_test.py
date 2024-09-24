# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import IpVlan

from .testlib import assertlib
from .testlib.env import nm_minor_version

ETH1 = "eth1"
IPVLAN0 = "ipvlan0"


@pytest.mark.skipif(
    nm_minor_version() < 51,
    reason=("IPVLAN is only supported by NetworkManager 1.51+"),
)
@pytest.mark.parametrize(
    IpVlan.MODE,
    [
        IpVlan.Mode.L2,
        IpVlan.Mode.L3,
        IpVlan.Mode.L3S,
    ],
)
def test_add_ipvlan_multiple_modes(eth1_up, mode):
    with ipvlan_interface(IPVLAN0, mode, False, False) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_absent(IPVLAN0)


@pytest.mark.skipif(
    nm_minor_version() < 51,
    reason=("IPVLAN is only supported by NetworkManager 1.51+"),
)
def test_add_ipvlan_private_on(eth1_up):
    with ipvlan_interface(
        IPVLAN0, IpVlan.Mode.L2, True, False
    ) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_absent(IPVLAN0)


@pytest.mark.skipif(
    nm_minor_version() < 51,
    reason=("IPVLAN is only supported by NetworkManager 1.51+"),
)
def test_add_ipvlan_vepa_on(eth1_up):
    with ipvlan_interface(
        IPVLAN0, IpVlan.Mode.L2, False, True
    ) as desired_state:
        assertlib.assert_state(desired_state)
    assertlib.assert_absent(IPVLAN0)


@pytest.mark.skipif(
    nm_minor_version() < 51,
    reason=("IPVLAN is only supported by NetworkManager 1.51+"),
)
def test_edit_ipvlan(eth1_up):
    with ipvlan_interface(
        IPVLAN0, IpVlan.Mode.L2, False, False
    ) as desired_state:
        assertlib.assert_state(desired_state)
        desired_state[Interface.KEY][0][IpVlan.CONFIG_SUBTREE][
            IpVlan.MODE
        ] = IpVlan.Mode.L3
        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)
    assertlib.assert_absent(IPVLAN0)


@contextmanager
def ipvlan_interface(ifname, mode, private, vepa):
    d_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.IPVLAN,
                Interface.STATE: InterfaceState.UP,
                IpVlan.CONFIG_SUBTREE: {
                    IpVlan.BASE_IFACE: ETH1,
                    IpVlan.MODE: mode,
                    IpVlan.PRIVATE: private,
                    IpVlan.VEPA: vepa,
                },
            }
        ]
    }
    try:
        libnmstate.apply(d_state)
        yield d_state
    finally:
        d_state[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(d_state)
