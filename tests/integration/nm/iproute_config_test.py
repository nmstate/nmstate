#
# Copyright (c) 2020-2022 Red Hat, Inc.
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

import time

import pytest
import yaml

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import Route

from ..testlib import cmdlib
from ..testlib.dummy import nm_unmanaged_dummy
from ..testlib.assertlib import assert_absent
from ..testlib.assertlib import assert_state_match
from ..testlib.statelib import show_only

BOND99 = "bond99"
DUMMY1 = "dummy1"
DUMMY2 = "dummy2"
IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:1::2"


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


@pytest.mark.xfail(
    reason="https://bugzilla.redhat.com/2070855",
    strict=False,
)
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
def unmanged_dummy1_with_static_ip():
    with nm_unmanaged_dummy(DUMMY1):
        cmdlib.exec_cmd(
            f"ip addr add {IPV4_ADDRESS1}/24 dev {DUMMY1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"ip addr add {IPV6_ADDRESS1}/64 dev {DUMMY1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"ip -6 route add default via {IPV6_ADDRESS2} "
            f"dev {DUMMY1}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip route add default via {IPV4_ADDRESS2} dev {DUMMY1} "
            "metric 101".split(),
            check=True,
        )
        yield


def test_convert_unmanged_interface_to_managed(unmanged_dummy1_with_static_ip):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.UP,
                }
            ]
        }
    )

    desired_state = yaml.load(
        """
---
interfaces:
- name: dummy1
  state: up
  mtu: 1500
  ipv4:
    address:
    - ip: 192.0.2.251
      prefix-length: 24
    dhcp: false
    enabled: true
  ipv6:
    address:
      - ip: 2001:db8:1::1
        prefix-length: 64
    autoconf: false
    dhcp: false
    enabled: true""",
        Loader=yaml.SafeLoader,
    )

    assert_state_match(desired_state)
    # assert_state_match() only check Interface.KEY,
    # so we verify route manually
    cur_state = libnmstate.show()
    gw4_found = False
    gw6_found = False
    for route in cur_state[Route.KEY][Route.CONFIG]:
        if (
            route[Route.DESTINATION] == "0.0.0.0/0"
            and route[Route.NEXT_HOP_INTERFACE] == DUMMY1
            and route[Route.NEXT_HOP_ADDRESS] == IPV4_ADDRESS2
        ):
            gw4_found = True
        if (
            route[Route.DESTINATION] == "::/0"
            and route[Route.NEXT_HOP_INTERFACE] == DUMMY1
            and route[Route.NEXT_HOP_ADDRESS] == IPV6_ADDRESS2
        ):
            gw6_found = True
    assert gw4_found
    assert gw6_found


@pytest.fixture
def external_managed_veth1_with_static_ip():
    cmdlib.exec_cmd(
        "ip link add veth1 type veth peer veth1-ep".split(), check=True
    )
    cmdlib.exec_cmd("ip link set veth1-ep up".split(), check=True)
    cmdlib.exec_cmd("ip link set veth1 up".split(), check=True)
    cmdlib.exec_cmd("nmcli d set veth1 managed true".split(), check=True)
    cmdlib.exec_cmd("ip addr add 192.0.2.2/24 dev veth1".split(), check=True)
    cmdlib.exec_cmd(
        "ip addr add 2001:db8:f::1/64 dev veth1".split(), check=True
    )
    yield
    cmdlib.exec_cmd("ip link del veth1".split())


def test_external_managed_veth_with_static_ip(
    external_managed_veth1_with_static_ip,
):
    iface_state = show_only(("veth1",))[Interface.KEY][0]
    ipv4_info = iface_state[Interface.IPV4]
    ipv6_info = iface_state[Interface.IPV6]

    assert ipv4_info[InterfaceIPv4.ENABLED]
    assert ipv4_info[InterfaceIPv4.ADDRESS] == [
        {
            InterfaceIPv4.ADDRESS_IP: "192.0.2.2",
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
        }
    ]
    assert ipv6_info[InterfaceIPv6.ENABLED]
    assert {
        InterfaceIPv6.ADDRESS_IP: "2001:db8:f::1",
        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
    } in ipv6_info[InterfaceIPv6.ADDRESS]


def test_bring_unmanaged_iface_down(unmanged_dummy1_with_static_ip):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.DOWN,
                }
            ]
        }
    )
    assert_absent(DUMMY1)


def test_mark_unmanaged_iface_absent(unmanged_dummy1_with_static_ip):
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
    assert_absent(DUMMY1)


@pytest.fixture
def external_managed_dummy1_with_autoconf():
    cmdlib.exec_cmd(f"ip link add {DUMMY1} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {DUMMY1} up".split(), check=True)
    cmdlib.exec_cmd(
        f"ip addr add {IPV6_ADDRESS1}/64 dev {DUMMY1} "
        "valid_lft 2000 preferred_lft 1000".split(),
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


# Make sure we are not impacted by undesired iface which is holding invalid
# setting(here is DHCPv6 off with autoconf on)
def test_external_managed_iface_with_autoconf_enabled(
    eth1_up,
    external_managed_dummy1_with_autoconf,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                }
            ]
        }
    )
