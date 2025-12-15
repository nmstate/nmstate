# SPDX-License-Identifier: Apache-2.0

import time
from subprocess import SubprocessError

import pytest

import libnmstate

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import VLAN


from ..testlib import assertlib
from ..testlib import cmdlib

TEST_VLAN = "test_vlan0"
TEST_PROFILE_NAME = "0eth1"


@pytest.fixture
def eth1_up_with_two_profiles(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
    )
    cmdlib.exec_cmd(
        "nmcli c add type ethernet ifname eth1 "
        f"connection.id {TEST_PROFILE_NAME} ipv4.method disabled "
        "ipv6.method disabled".split(),
        check=True,
    )
    cmdlib.exec_cmd(f"nmcli c up {TEST_PROFILE_NAME}".split(), check=True)
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    cmdlib.exec_cmd(f"nmcli c del {TEST_PROFILE_NAME}".split())


# To reproduce the ordinal issue in https://bugzilla.redhat.com/2202999 ,
# multiple try is required
def test_vlan_parent_has_two_profiles(eth1_up_with_two_profiles):
    try:
        for _ in range(0, 5):
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: TEST_VLAN,
                            Interface.TYPE: InterfaceType.VLAN,
                            Interface.STATE: InterfaceState.UP,
                            VLAN.CONFIG_SUBTREE: {
                                VLAN.ID: 101,
                                VLAN.BASE_IFACE: "eth1",
                            },
                        }
                    ]
                }
            )
            time.sleep(1)
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: TEST_VLAN,
                        Interface.TYPE: InterfaceType.VLAN,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )


@pytest.fixture
def eth1_100_with_empty_interface_name(eth1_up):
    cmdlib.exec_cmd(
        "nmcli c add type vlan con-name eth1.100 dev eth1 id 100 "
        "ipv4.method disabled ipv6.method disabled".split(),
        check=True,
    )
    yield


# https://issues.redhat.com/browse/RHEL-92916
@pytest.mark.tier1
def test_delete_vlan_connection_with_empty_interface_name(
    eth1_100_with_empty_interface_name,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1.100",
                    Interface.TYPE: InterfaceType.VLAN,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )

    assertlib.assert_absent("eth1.100")
    with pytest.raises(SubprocessError):
        cmdlib.exec_cmd("nmcli c show eth1.100".split(), check=True)
