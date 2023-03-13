# SPDX-License-Identifier: LGPL-2.1-or-later

import time

import pytest

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from ..testlib import cmdlib
from ..testlib.iproutelib import iproute_get_ip_addrs_with_order

BOND99 = "bond99"
DUMMY1 = "dummy1"
DUMMY2 = "dummy2"

IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"


@pytest.fixture
def bond99_with_dummy_port_by_iproute():
    cmdlib.exec_cmd(f"ip link add {DUMMY1} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link add {DUMMY2} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link add {BOND99} type bond".split(), check=True)
    cmdlib.exec_cmd(
        f"ip link set {DUMMY1} master {BOND99}".split(), check=True
    )
    cmdlib.exec_cmd(
        f"ip link set {DUMMY2} master {BOND99}".split(), check=True
    )
    cmdlib.exec_cmd(f"ip link set {DUMMY1} up".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {DUMMY2} up".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {BOND99} up".split(), check=True)
    time.sleep(1)  # Wait NM mark them as managed
    yield
    cmdlib.exec_cmd(f"nmcli c del {BOND99}".split())
    cmdlib.exec_cmd(f"nmcli c del {DUMMY1}".split())
    cmdlib.exec_cmd(f"nmcli c del {DUMMY2}".split())
    cmdlib.exec_cmd(f"ip link del {DUMMY1}".split())
    cmdlib.exec_cmd(f"ip link del {DUMMY2}".split())
    cmdlib.exec_cmd(f"ip link del {BOND99}".split())


def test_external_managed_subordnates(bond99_with_dummy_port_by_iproute):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: BOND99,
                    Interface.STATE: InterfaceState.UP,
                    Bond.CONFIG_SUBTREE: {
                        # Change the bond mode to force a reactivate
                        Bond.MODE: BondMode.ACTIVE_BACKUP,
                        Bond.PORT: [DUMMY1, DUMMY2],
                    },
                }
            ]
        }
    )


@pytest.fixture
def external_managed_dummy1_with_ips():
    cmdlib.exec_cmd(f"ip link add {DUMMY1} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {DUMMY1} up".split(), check=True)
    cmdlib.exec_cmd(
        f"ip addr add {IPV4_ADDRESS2}/24 dev {DUMMY1}".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"ip addr add {IPV4_ADDRESS1}/24 dev {DUMMY1}".split(),
        check=True,
    )
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    cmdlib.exec_cmd(f"ip link del {DUMMY1}".split(), check=False)


def test_perserve_ip_order_of_external_managed_nic(
    external_managed_dummy1_with_ips,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
    )
    ip_addrs = iproute_get_ip_addrs_with_order(iface=DUMMY1, is_ipv6=False)
    assert ip_addrs[0] == IPV4_ADDRESS2
    assert ip_addrs[1] == IPV4_ADDRESS1
