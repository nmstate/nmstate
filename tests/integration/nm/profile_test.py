#
# Copyright (c) 2019-2021 Red Hat, Inc.
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

from contextlib import contextmanager
import os

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge
from libnmstate.schema import Route

from ..testlib import assertlib
from ..testlib import cmdlib
from ..testlib import statelib
from ..testlib.env import is_k8s
from ..testlib.ovslib import Bridge as OvsBridge


DUMMY0_IFNAME = "dummy0"
TEST_BRIDGE0 = "linux-br0"
TEST_OVS_BRIDGE0 = "br0"
TEST_OVS_PORT0 = "ovs0"
IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV6_ADDRESS1 = "2001:db8:1::1"


NMCLI_CON_ADD_DUMMY_CMD = [
    "nmcli",
    "con",
    "add",
    "type",
    "dummy",
    "con-name",
    "testProfile",
    "connection.autoconnect",
    "no",
    "ifname",
    DUMMY0_IFNAME,
]

NMCLI_CON_ADD_AUTOCONNECT_DUMMY_CMD = [
    "nmcli",
    "con",
    "add",
    "type",
    "dummy",
    "con-name",
    "testProfile",
    "connection.autoconnect",
    "yes",
    "ifname",
    DUMMY0_IFNAME,
]

NMCLI_CON_ADD_ETH_CMD = [
    "nmcli",
    "con",
    "add",
    "type",
    "ethernet",
    "con-name",
    "testProfile",
    "connection.autoconnect",
    "no",
    "ifname",
    "eth1",
]

NMCLI_CON_UP_TEST_PROFILE_CMD = [
    "nmcli",
    "con",
    "up",
    "testProfile",
]

NM_PROFILE_DIRECTORY = "/etc/NetworkManager/system-connections/"

ETH_PROFILE_DIRECTORY = "/etc/sysconfig/network-scripts/"

MEMORY_ONLY_PROFILE_DIRECTORY = "/run/NetworkManager/system-connections/"

MAC0 = "02:FF:FF:FF:FF:00"


@pytest.mark.tier1
def test_delete_new_interface_inactive_profiles(dummy_inactive_profile):
    with dummy_interface(dummy_inactive_profile):
        profile_exists = _profile_exists(
            NM_PROFILE_DIRECTORY + "testProfile.nmconnection"
        )
        assert not profile_exists


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=AssertionError,
    strict=False,
)
def test_delete_existing_interface_inactive_profiles(eth1_up):
    with create_inactive_profile(eth1_up[Interface.KEY][0][Interface.NAME]):
        eth1_up[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(eth1_up)
        profile_exists = _profile_exists(
            ETH_PROFILE_DIRECTORY + "ifcfg-testProfile"
        )
        assert not profile_exists


def test_rename_existing_interface_active_profile(eth1_up):
    cloned_profile_name = "testProfile"
    with cloned_active_profile(
        cloned_profile_name, eth1_up[Interface.KEY][0][Interface.NAME]
    ):
        eth1_up[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(eth1_up)
        assert _profile_exists(ETH_PROFILE_DIRECTORY + "ifcfg-testProfile")


@contextmanager
def dummy_interface(ifname, save_to_disk=True):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    libnmstate.apply(desired_state, save_to_disk=save_to_disk)
    try:
        yield desired_state
    finally:
        dummy0_dstate = desired_state[Interface.KEY][0]
        dummy0_dstate[Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(desired_state)


@pytest.fixture
def dummy_inactive_profile():
    cmdlib.exec_cmd(NMCLI_CON_ADD_DUMMY_CMD)
    profile_exists = _profile_exists(
        NM_PROFILE_DIRECTORY + "testProfile.nmconnection"
    )
    assert profile_exists
    try:
        yield DUMMY0_IFNAME
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection("testProfile"))


@pytest.fixture
def dummy_active_profile():
    cmdlib.exec_cmd(NMCLI_CON_ADD_AUTOCONNECT_DUMMY_CMD)
    profile_exists = _profile_exists(
        NM_PROFILE_DIRECTORY + "testProfile.nmconnection"
    )
    assert profile_exists
    try:
        yield DUMMY0_IFNAME
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection("testProfile"))


@contextmanager
def cloned_active_profile(con_name, source):
    cmdlib.exec_cmd(["nmcli", "con", "clone", "id", source, con_name])
    cmdlib.exec_cmd(_nmcli_delete_connection(source))
    cmdlib.exec_cmd(NMCLI_CON_UP_TEST_PROFILE_CMD)
    profile_exists = _profile_exists(
        ETH_PROFILE_DIRECTORY + f"ifcfg-{con_name}"
    )
    assert profile_exists
    try:
        yield
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection(con_name))


@contextmanager
def create_inactive_profile(con_name):
    cmdlib.exec_cmd(_nmcli_deactivate_connection(con_name))
    cmdlib.exec_cmd(NMCLI_CON_ADD_ETH_CMD)
    profile_exists = _profile_exists(
        ETH_PROFILE_DIRECTORY + "ifcfg-testProfile"
    )
    assert profile_exists
    try:
        yield
    finally:
        cmdlib.exec_cmd(_nmcli_delete_connection("testProfile"))


def test_state_down_preserving_config():
    with dummy_interface(DUMMY0_IFNAME) as desired_state:
        iface_state = desired_state[Interface.KEY][0]
        iface_state[Interface.MAC] = MAC0
        iface_state[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
        libnmstate.apply(desired_state)
        state_before_down = statelib.show_only((DUMMY0_IFNAME,))

        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DUMMY0_IFNAME,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )

        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DUMMY0_IFNAME,
                        Interface.TYPE: InterfaceType.DUMMY,
                        Interface.STATE: InterfaceState.UP,
                    }
                ]
            }
        )

        assertlib.assert_state_match(state_before_down)


@pytest.fixture
def dummy0_with_down_profile():
    with dummy_interface(DUMMY0_IFNAME) as desired_state:
        iface_state = desired_state[Interface.KEY][0]
        iface_state[Interface.MAC] = MAC0
        iface_state[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
        libnmstate.apply(desired_state)
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: DUMMY0_IFNAME,
                        Interface.STATE: InterfaceState.DOWN,
                    }
                ]
            }
        )
        yield desired_state


def test_state_absent_can_remove_down_profiles(dummy0_with_down_profile):
    state_before_down = dummy0_with_down_profile
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0_IFNAME,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0_IFNAME,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
    )

    # Sinec absent already removed the down profile, if we bring the same
    # interface up, it should contain different states than before
    with pytest.raises(AssertionError):
        assertlib.assert_state_match(state_before_down)


def test_create_memory_only_profile_new_interface():
    with dummy_interface(DUMMY0_IFNAME, save_to_disk=False):
        assert not _profile_exists(
            NM_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )
        assert _profile_exists(
            MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )

    assert not _profile_exists(
        MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
    )


def test_create_memory_only_profile_edit_interface():
    with dummy_interface(DUMMY0_IFNAME) as dstate:
        assert not _profile_exists(
            MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )
        dstate[Interface.KEY][0][Interface.MTU] = 2000
        libnmstate.apply(dstate, save_to_disk=False)
        assert _profile_exists(NM_PROFILE_DIRECTORY + "dummy0.nmconnection")
        assert _profile_exists(
            MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
        )

    assert not _profile_exists(
        MEMORY_ONLY_PROFILE_DIRECTORY + "dummy0.nmconnection"
    )


def test_memory_only_profile_absent_interface():
    with dummy_interface(DUMMY0_IFNAME) as dstate:
        dstate[Interface.KEY][0][Interface.STATE] = InterfaceState.ABSENT
        libnmstate.apply(dstate, save_to_disk=False)
        assertlib.assert_absent(DUMMY0_IFNAME)
        assert _profile_exists(NM_PROFILE_DIRECTORY + "dummy0.nmconnection")

    assertlib.assert_absent(DUMMY0_IFNAME)


def _nmcli_deactivate_connection(con_name):
    return ["nmcli", "con", "down", con_name]


def _nmcli_delete_connection(con_name):
    return ["nmcli", "con", "delete", con_name]


def _profile_exists(profile_name):
    return os.path.isfile(profile_name)


@pytest.fixture
def eth1_with_two_profiles(eth1_up):
    # The newly profile should be activated, this is the key to reproduce
    # the problem
    cmdlib.exec_cmd(
        "nmcli c add type ethernet ifname eth1 connection.id foo "
        "ipv4.method disabled ipv6.method disabled ".split(),
        check=True,
    )
    cmdlib.exec_cmd("nmcli c up foo".split())
    yield
    cmdlib.exec_cmd("nmcli c del foo".split())


def test_linux_bridge_with_port_holding_two_profiles(eth1_with_two_profiles):
    try:
        desired_state = {
            Interface.KEY: [
                {
                    Interface.NAME: "br0",
                    Interface.TYPE: InterfaceType.LINUX_BRIDGE,
                    Interface.STATE: InterfaceState.UP,
                    LinuxBridge.CONFIG_SUBTREE: {
                        LinuxBridge.OPTIONS_SUBTREE: {
                            LinuxBridge.STP_SUBTREE: {
                                LinuxBridge.STP.ENABLED: False
                            }
                        },
                        LinuxBridge.PORT_SUBTREE: [
                            {LinuxBridge.Port.NAME: "eth1"}
                        ],
                    },
                    Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                    Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                    Interface.MTU: 1500,
                },
                {
                    Interface.NAME: "eth1",
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                    Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                    Interface.MTU: 1500,
                },
            ]
        }
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "br0",
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=NmstateValueError,
    strict=False,
)
def test_converting_memory_only_profile_to_persistent():
    with dummy_interface(DUMMY0_IFNAME, save_to_disk=False) as dstate:
        libnmstate.apply(dstate, save_to_disk=True)
        assert _profile_exists(NM_PROFILE_DIRECTORY + "dummy0.nmconnection")

    assertlib.assert_absent(DUMMY0_IFNAME)


@pytest.fixture
def ovs_bridge_with_internal_port():
    bridge = OvsBridge(TEST_OVS_BRIDGE0)
    bridge.add_internal_port(TEST_OVS_PORT0)
    with bridge.create():
        yield bridge.state


def test_ovs_profile_been_delete_by_state_absent(
    ovs_bridge_with_internal_port,
):
    assert _profile_exists(NM_PROFILE_DIRECTORY + "ovs0.nmconnection")
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_OVS_PORT0,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    assert not _profile_exists(NM_PROFILE_DIRECTORY + "ovs0.nmconnection")


@pytest.fixture
def multiconnect_profile_with_ip_disabled():
    cmdlib.exec_cmd("nmcli c del eth1".split(), check=True)
    cmdlib.exec_cmd(
        "nmcli c add type ethernet connection.id nmstate-test-default "
        "connection.multi-connect multiple "
        "ipv4.method disabled ipv6.method disabled".split(),
        check=True,
    )
    yield
    cmdlib.exec_cmd("nmcli c del nmstate-test-default".split(), check=False)


# We cannot use eth1_up which create a dedicate profile for eth1.
# In order to test the multiconnect feature, we should do it manually.
def test_set_static_ip_with_multiconnect_profile(
    eth1_up,
    multiconnect_profile_with_ip_disabled,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)
    assert cmdlib.exec_cmd(
        "nmcli -g ipv4.method c show nmstate-test-default".split()
    ) == (
        0,
        "disabled\n",
        "",
    )
    assert cmdlib.exec_cmd("nmcli -g ipv4.method c show eth1".split()) == (
        0,
        "manual\n",
        "",
    )


@pytest.fixture
def eth1_up_static_ipv4_mtu_1400(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Interface.MTU: 1400,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                }
            ]
        }
    )
    yield


def test_preserve_existing_wire_setting(eth1_up_static_ipv4_mtu_1400):
    libnmstate.apply(
        {
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.DESTINATION: "198.51.100.0/24",
                        Route.NEXT_HOP_ADDRESS: IPV4_ADDRESS2,
                        Route.NEXT_HOP_INTERFACE: "eth1",
                    }
                ]
            }
        }
    )

    assert cmdlib.exec_cmd(
        "nmcli -g 802-3-ethernet.mtu c show eth1".split()
    ) == (
        0,
        "1400\n",
        "",
    )


@pytest.mark.tier1
def test_nmstate_do_not_modify_conn_name(dummy_active_profile):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0_IFNAME,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.STATE: InterfaceState.UP,
                    Interface.MTU: 1400,
                },
            ]
        }
    )

    _, out, _ = cmdlib.exec_cmd(
        "nmcli -g 802-3-ethernet.mtu c show testProfile".split(), check=True
    )
    assert "1400" in out
