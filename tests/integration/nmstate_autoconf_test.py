# SPDX-License-Identifier: Apache-2.0

import os
import pytest
import time

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import LLDP
from libnmstate.schema import VLAN

from .testlib import cmdlib
from .testlib import statelib
from .testlib.veth import veth_interface


LLDPTEST1 = "lldptest1"
LLDPTEST1_PEER = "lldptest1.peer"
LLDPTEST2 = "lldptest2"
LLDPTEST2_PEER = "lldptest2.peer"
LLDPTEST3 = "lldptest3"
LLDPTEST3_PEER = "lldptest3.peer"
BOND50 = "bond50"
VLAN_PRODNET = "prod-net"
VLAN_MGMTNET = "mgmt-net"

AUTOCONF_CMD = "nmstate-autoconf"

LLDP_BASIC_STATE = {
    Interface.KEY: [
        {
            Interface.NAME: LLDPTEST1,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.VETH,
        },
        {
            Interface.NAME: LLDPTEST2,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.VETH,
        },
        {
            Interface.NAME: LLDPTEST3,
            Interface.STATE: InterfaceState.UP,
            Interface.TYPE: InterfaceType.VETH,
        },
    ]
}


@pytest.fixture(scope="module")
def lldpifaces_env():
    with veth_interface(LLDPTEST1, LLDPTEST1_PEER), veth_interface(
        LLDPTEST2, LLDPTEST2_PEER
    ), veth_interface(LLDPTEST3, LLDPTEST3_PEER):
        yield
        _iface_cleanup(BOND50)
        _iface_cleanup(VLAN_MGMTNET)
        _iface_cleanup(VLAN_PRODNET)


def test_autoconf_prodnet_and_mgmtnet(lldpifaces_env):
    with lldp_enabled(LLDP_BASIC_STATE):
        _send_lldp_packet(LLDPTEST1_PEER, "lldp_prodnet.pcap")
        _send_lldp_packet(LLDPTEST2_PEER, "lldp_prodnet.pcap")
        _send_lldp_packet(LLDPTEST3_PEER, "lldp_mgmtnet.pcap")

        cmdlib.exec_cmd(AUTOCONF_CMD.split(), check=True)
        bond_cstate = statelib.show_only((BOND50,))[Interface.KEY][0]
        assert LLDPTEST1 in bond_cstate[Bond.CONFIG_SUBTREE][Bond.PORT]
        assert LLDPTEST2 in bond_cstate[Bond.CONFIG_SUBTREE][Bond.PORT]

        vlan_prod = statelib.show_only((VLAN_PRODNET,))[Interface.KEY][0]
        assert BOND50 == vlan_prod[VLAN.CONFIG_SUBTREE][VLAN.BASE_IFACE]

        vlan_mgmt = statelib.show_only((VLAN_MGMTNET,))[Interface.KEY][0]
        assert LLDPTEST3 == vlan_mgmt[VLAN.CONFIG_SUBTREE][VLAN.BASE_IFACE]


def test_autoconf_all_prodnet(lldpifaces_env):
    with lldp_enabled(LLDP_BASIC_STATE):
        _send_lldp_packet(LLDPTEST1_PEER, "lldp_prodnet.pcap")
        _send_lldp_packet(LLDPTEST2_PEER, "lldp_prodnet.pcap")
        _send_lldp_packet(LLDPTEST3_PEER, "lldp_prodnet.pcap")

        cmdlib.exec_cmd(AUTOCONF_CMD, check=True)
        bond_cstate = statelib.show_only((BOND50,))[Interface.KEY][0]
        assert LLDPTEST1 in bond_cstate[Bond.CONFIG_SUBTREE][Bond.PORT]
        assert LLDPTEST2 in bond_cstate[Bond.CONFIG_SUBTREE][Bond.PORT]
        assert LLDPTEST3 in bond_cstate[Bond.CONFIG_SUBTREE][Bond.PORT]

        vlan_prod = statelib.show_only((VLAN_PRODNET,))[Interface.KEY][0]
        assert BOND50 == vlan_prod[VLAN.CONFIG_SUBTREE][VLAN.BASE_IFACE]


@contextmanager
def lldp_enabled(ifstate):
    for iface in ifstate.get(Interface.KEY, []):
        iface[LLDP.CONFIG_SUBTREE] = {LLDP.ENABLED: True}

    libnmstate.apply(ifstate)
    try:
        yield
    finally:
        for iface in ifstate.get(Interface.KEY, []):
            iface[LLDP.CONFIG_SUBTREE][LLDP.ENABLED] = False
        libnmstate.apply(ifstate)


def _send_lldp_packet(ifname, pcap):
    test_dir = os.path.dirname(os.path.realpath(__file__))
    cmdlib.exec_cmd(
        f"tcpreplay --intf1={ifname} "
        f"{test_dir}/test_captures/{pcap}".split(),
        check=True,
    )
    time.sleep(1)


def _iface_cleanup(ifname):
    ifstate = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.STATE: InterfaceState.ABSENT,
            },
        ]
    }
    libnmstate.apply(ifstate)
