#
# Copyright (c) 2021 Red Hat, Inc.
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
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from ..testlib import assertlib
from ..testlib import cmdlib


DUMMY0 = "dummy0"
ETH1 = "eth1"


@pytest.fixture
def unmanaged_eth1_with_static_gw():
    try:
        cmdlib.exec_cmd(f"nmcli connection delete {ETH1}".split(), check=False)
        cmdlib.exec_cmd(f"nmcli dev set {ETH1} managed no".split(), check=True)
        cmdlib.exec_cmd(
            f"ip addr add 192.0.2.2/24 dev {ETH1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"ip route add default via 192.0.2.1 dev {ETH1} proto "
            "static".split(),
            check=True,
        )
        cmdlib.exec_cmd(f"ip link set {ETH1} up".split(), check=True)
        yield
    finally:
        cmdlib.exec_cmd(
            f"ip route del default via 192.0.2.1 dev {ETH1}".split(),
            check=True,
        )

        cmdlib.exec_cmd(
            f"ip addr del 192.0.2.2/24 dev {ETH1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"nmcli dev set {ETH1} managed yes".split(), check=True
        )


def test_set_auto_dns_with_unamanged_iface_with_static_gw(
    unmanaged_eth1_with_static_gw,
):
    desired_state = {
        DNS.KEY: {DNS.CONFIG: {DNS.SERVER: ["1.1.1.1"]}},
        Interface.KEY: [
            {
                Interface.NAME: DUMMY0,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.AUTO_DNS: False,
                    InterfaceIPv4.AUTO_ROUTES: True,
                    InterfaceIPv4.AUTO_GATEWAY: True,
                },
            }
        ],
    }
    libnmstate.apply(desired_state)
    try:
        assertlib.assert_state(desired_state)
    finally:
        absent_state = {
            DNS.KEY: {DNS.CONFIG: {DNS.SERVER: []}},
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ],
        }
        libnmstate.apply(absent_state)
