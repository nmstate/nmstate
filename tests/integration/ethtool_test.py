# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import os
import time

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.schema import Ethtool
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import Veth

from .testlib import assertlib
from .testlib import cmdlib
from .testlib.env import is_fedora
from .testlib.env import kernel_newer_than
from .testlib.statelib import show_only

MAX_NETDEVSIM_WAIT_TIME = 5

TEST_NETDEVSIM_NIC = "sim0"


@contextmanager
def netdevsim_interface(ifname):
    try:
        cmdlib.exec_cmd("modprobe netdevsim".split(), check=True)
        with open("/sys/bus/netdevsim/new_device", "w") as fd:
            fd.write("1 1")

        done = False
        for i in range(0, MAX_NETDEVSIM_WAIT_TIME):
            time.sleep(1)
            i += 1
            nics = _get_cur_netdevsim_ifnames()
            if nics:
                _ip_iface_rename(nics[0], ifname)
                done = True
                break
        assert done
        yield
    finally:
        cmdlib.exec_cmd("modprobe -r netdevsim".split())


def _get_cur_netdevsim_ifnames():
    return os.listdir("/sys/devices/netdevsim1/net/")


def _ip_iface_rename(src_name, dst_name):
    cmdlib.exec_cmd(f"ip link set {src_name} down".split(), check=True)
    cmdlib.exec_cmd(
        f"ip link set {src_name} name {dst_name}".split(), check=True
    )


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or not is_fedora(),
    reason=("Ethtool pause test need netdevsim kernel module"),
)
def test_ethtool_pause_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: False,
                Ethtool.Pause.RX: True,
                Ethtool.Pause.TX: True,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or not is_fedora(),
    reason=("Ethtool pause test need netdevsim kernel module"),
)
def test_ethtool_pause_off_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: False,
                Ethtool.Pause.RX: False,
                Ethtool.Pause.TX: False,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=("CI does not have ethtool kernel option enabled"),
)
def test_ethtool_feature_using_ethtool_cli_alias_rx_checksumming(eth1_up):
    desire_iface_state = {
        Interface.NAME: "eth1",
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {"rx-checksumming": False}
        },
    }
    libnmstate.apply({Interface.KEY: [desire_iface_state]})

    desire_feature = desire_iface_state[Ethtool.CONFIG_SUBTREE][
        Ethtool.Feature.CONFIG_SUBTREE
    ]
    desire_feature.pop("rx-checksumming")
    desire_feature["rx-checksum"] = False

    assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})


def veth_support_tso():
    """True if eth1 reports tx-tcp-segmentation in nmstate ethtool query."""
    try:
        ifaces = show_only(["eth1"]).get(Interface.KEY) or []
        if not ifaces:
            return False
        features = (
            ifaces[0]
            .get(Ethtool.CONFIG_SUBTREE, {})
            .get(Ethtool.Feature.CONFIG_SUBTREE, {})
        )
    except (IndexError, KeyError, TypeError):
        return False
    return "tx-tcp-segmentation" in features


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=("CI does not have ethtool kernel option enabled"),
)
@pytest.mark.parametrize(
    "feature_key",
    ("tso", "tcp-segmentation-offload", "tx-tcp-segmentation"),
)
def test_ethtool_tx_tcp_segmentation_aliases_on_eth1(eth1_up, feature_key):
    """
    Apply TSO on eth1 (session veth) using CLI-style aliases and the kernel
    name, then assert against canonical 'tx-tcp-segmentation' in show/verify.
    """
    # Use pytest.skip here, not @pytest.mark.skipif(...):
    # skipif is evaluated at collection time, before fixtures like
    # eth1_up create or bring up eth1, so show_only(["eth1"])
    # would run too early and skip wrongly or
    # flap depending on session/fixture order.
    if not veth_support_tso():
        pytest.skip(
            "eth1 does not list tx-tcp-segmentation in"
            " changeable ethtool features"
        )

    for enabled in (True, False):
        apply_state = {
            Interface.NAME: "eth1",
            Ethtool.CONFIG_SUBTREE: {
                Ethtool.Feature.CONFIG_SUBTREE: {feature_key: enabled}
            },
        }
        libnmstate.apply({Interface.KEY: [apply_state]})
        expect_match = {
            Interface.NAME: "eth1",
            Ethtool.CONFIG_SUBTREE: {
                Ethtool.Feature.CONFIG_SUBTREE: {
                    "tx-tcp-segmentation": enabled
                }
            },
        }
        assertlib.assert_state_match({Interface.KEY: [expect_match]})


def test_ethtool_invalid_feature(eth1_up):
    desire_iface_state = {
        Interface.NAME: "eth1",
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {"no_exist_feature": False}
        },
    }
    with pytest.raises(NmstateValueError):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})


@pytest.mark.skipif(
    not os.environ.get("TEST_REAL_NIC"),
    reason="Need to define TEST_REAL_NIC for ethtool ring test",
)
def test_ethtool_ring_set_rx():
    desire_iface_state = {
        Interface.NAME: os.environ.get("TEST_REAL_NIC"),
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Ring.CONFIG_SUBTREE: {Ethtool.Ring.RX: 256}
        },
    }
    libnmstate.apply({Interface.KEY: [desire_iface_state]})

    assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or not is_fedora(),
    reason=("Ethtool pause test need netdevsim kernel module in Fedora 34+"),
)
def test_ethtool_coalesce_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Coalesce.CONFIG_SUBTREE: {
                Ethtool.Coalesce.TX_USECS: 100,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.fixture
def veth1_with_ethtool_feature_highdma_false():
    interface_name = "veth1"
    peer_interface_name = f"{interface_name}.ep"
    iface_state = {
        Interface.NAME: interface_name,
        Interface.TYPE: Veth.TYPE,
        Interface.STATE: InterfaceState.UP,
        Veth.CONFIG_SUBTREE: {Veth.PEER: peer_interface_name},
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {
                "highdma": False,
            }
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})
    yield iface_state
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: peer_interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ],
        },
        verify_change=False,
    )


@pytest.fixture
def veth1_with_ethtool_feature_highdma_true():
    interface_name = "veth1"
    peer_interface_name = f"{interface_name}.ep"
    iface_state = {
        Interface.NAME: interface_name,
        Interface.TYPE: Veth.TYPE,
        Interface.STATE: InterfaceState.UP,
        Veth.CONFIG_SUBTREE: {Veth.PEER: peer_interface_name},
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Feature.CONFIG_SUBTREE: {
                "highdma": True,
            }
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})
    yield iface_state
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
                {
                    Interface.NAME: peer_interface_name,
                    Interface.STATE: InterfaceState.ABSENT,
                },
            ],
        },
        verify_change=False,
    )


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=("CI environment does not support ethtool via netlink yet"),
)
def test_ethtool_preserve_existing_ethtool_feature_setting(
    veth1_with_ethtool_feature_highdma_false,
):
    iface_state = veth1_with_ethtool_feature_highdma_false

    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: iface_state[Interface.NAME],
                    Interface.MTU: 1400,
                }
            ]
        }
    )
    iface_state[Interface.MTU] = 1400
    assertlib.assert_state_match({Interface.KEY: [iface_state]})


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or not is_fedora(),
    reason=("Ethtool fec test need netdevsim kernel module"),
)
def test_ethtool_fec_on_netdevsim():
    desire_iface_state = {
        Interface.NAME: TEST_NETDEVSIM_NIC,
        Ethtool.CONFIG_SUBTREE: {
            Ethtool.Fec.CONFIG_SUBTREE: {
                Ethtool.Fec.AUTO: False,
                Ethtool.Fec.MODE: Ethtool.Fec.MODE_OFF,
            }
        },
    }
    with netdevsim_interface(TEST_NETDEVSIM_NIC):
        libnmstate.apply({Interface.KEY: [desire_iface_state]})
        assertlib.assert_state_match({Interface.KEY: [desire_iface_state]})
    assertlib.assert_absent(TEST_NETDEVSIM_NIC)


@pytest.mark.skipif(
    not kernel_newer_than(6, 15),
    reason=(
        "Ethtool tx-tcp-accecn-segmentation is only support by kernel 6.15+"
    ),
)
def test_ethtool_hide_unsupported_feature(eth1_up):
    ethtool_info = show_only(["eth1"])["interfaces"][0][Ethtool.CONFIG_SUBTREE]

    assert (
        "tx-tcp-accecn-segmentation"
        not in ethtool_info[Ethtool.Feature.CONFIG_SUBTREE]
    )
