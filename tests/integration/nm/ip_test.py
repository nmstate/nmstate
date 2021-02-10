#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from ..testlib import cmdlib
from ..testlib import assertlib


IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.1"
IPV4_NET1 = "198.51.100.0/24"
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:1::2"
IPV6_NET1 = "2001:db8:a::/64"


def test_get_applied_config_for_dhcp_state_with_dhcp_enabeld_on_disk(eth1_up):
    iface_state = eth1_up[Interface.KEY][0]
    iface_name = iface_state[Interface.NAME]
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv4.method auto".split(), check=True
    )
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv6.method auto".split(), check=True
    )

    assertlib.assert_state_match({Interface.KEY: [iface_state]})


@pytest.fixture
def eth1_up_with_auto_ip(eth1_up):
    iface_name = eth1_up[Interface.KEY][0][Interface.NAME]
    iface_state = {
        Interface.NAME: iface_name,
        Interface.IPV4: {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: True,
        },
        Interface.IPV6: {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.DHCP: True,
            InterfaceIPv6.AUTOCONF: True,
        },
    }
    libnmstate.apply({Interface.KEY: [iface_state]})
    yield iface_state


def test_get_applied_config_for_dhcp_state_with_dhcp_disabled_on_disk(
    eth1_up_with_auto_ip,
):
    iface_state = eth1_up_with_auto_ip
    iface_name = iface_state[Interface.NAME]
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv4.method disabled".split(), check=True
    )
    cmdlib.exec_cmd(
        f"nmcli c modify {iface_name} ipv6.method disabled".split(), check=True
    )

    assertlib.assert_state_match({Interface.KEY: [iface_state]})


@pytest.fixture
def eth1_up_with_static_ip_and_route_by_iproute():
    cmdlib.exec_cmd("ip link set eth1 up".split(), check=True)
    cmdlib.exec_cmd(
        f"ip addr add {IPV4_ADDRESS1}/24 dev eth1 ".split(), check=True
    )
    cmdlib.exec_cmd(
        f"ip -6 addr add {IPV6_ADDRESS1}/64 dev eth1 ".split(), check=True
    )
    cmdlib.exec_cmd(
        f"ip route add {IPV4_NET1} via {IPV4_ADDRESS2} dev eth1 ".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"ip -6 route add {IPV6_NET1} via {IPV6_ADDRESS2} dev eth1 ".split(),
        check=True,
    )
    yield
    cmdlib.exec_cmd("nmcli c down eth1".split())
    cmdlib.exec_cmd("nmcli c del eth1".split())


def test_preserve_static_routes_created_by_iproute(
    eth1_up_with_static_ip_and_route_by_iproute,
):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                }
            ],
        }
    )

    assert (
        cmdlib.exec_cmd("nmcli -g ipv4.routes c show eth1".split())[1].strip()
        == "198.51.100.0/24 192.0.2.1 0 table=254"
    )
    assert (
        cmdlib.exec_cmd("nmcli -g ipv6.routes c show eth1".split())[1].strip()
        == r"2001\:db8\:a\:\:/64 2001\:db8\:1\:\:2 1024 table=254"
    )
