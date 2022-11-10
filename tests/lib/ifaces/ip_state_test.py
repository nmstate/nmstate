#
# Copyright (c) 2020 Red Hat, Inc.
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

from copy import deepcopy

import pytest

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from libnmstate.ifaces.base_iface import IPState

from ..testlib.constants import IPV4_ADDRESSES
from ..testlib.constants import IPV6_ADDRESS1
from ..testlib.constants import IPV6_ADDRESS1_FULL
from ..testlib.constants import IPV6_LINK_LOCAL_ADDRESS1
from ..testlib.constants import IPV6_ADDRESSES


parametrize_ip_ver = pytest.mark.parametrize(
    "ip_ver",
    [
        (
            Interface.IPV4,
            {
                InterfaceIPv4.ENABLED: True,
                InterfaceIPv4.ADDRESS: deepcopy(IPV4_ADDRESSES),
            },
        ),
        (
            Interface.IPV6,
            {
                InterfaceIPv6.ENABLED: True,
                InterfaceIPv6.ADDRESS: deepcopy(IPV6_ADDRESSES),
            },
        ),
    ],
    ids=["ipv4", "ipv6"],
)

parametrize_ip_ver_dynamic = pytest.mark.parametrize(
    "ip_ver_dynamic",
    [
        (
            Interface.IPV4,
            {
                InterfaceIPv4.ENABLED: True,
                InterfaceIPv4.DHCP: True,
                InterfaceIPv4.ADDRESS: [],
                InterfaceIPv4.AUTO_DNS: True,
                InterfaceIPv4.AUTO_GATEWAY: True,
                InterfaceIPv4.AUTO_ROUTES: True,
            },
        ),
        (
            Interface.IPV6,
            {
                InterfaceIPv6.ENABLED: True,
                InterfaceIPv6.DHCP: False,
                InterfaceIPv6.ADDRESS: [],
                InterfaceIPv6.AUTOCONF: True,
                InterfaceIPv6.AUTO_DNS: True,
                InterfaceIPv6.AUTO_GATEWAY: True,
                InterfaceIPv6.AUTO_ROUTES: True,
            },
        ),
        (
            Interface.IPV6,
            {
                InterfaceIPv6.ENABLED: True,
                InterfaceIPv6.DHCP: True,
                InterfaceIPv6.ADDRESS: [],
                InterfaceIPv6.AUTOCONF: False,
                InterfaceIPv6.AUTO_DNS: True,
                InterfaceIPv6.AUTO_GATEWAY: True,
                InterfaceIPv6.AUTO_ROUTES: True,
            },
        ),
        (
            Interface.IPV6,
            {
                InterfaceIPv6.ENABLED: True,
                InterfaceIPv6.DHCP: True,
                InterfaceIPv6.ADDRESS: [],
                InterfaceIPv6.AUTOCONF: True,
                InterfaceIPv6.AUTO_DNS: True,
                InterfaceIPv6.AUTO_GATEWAY: True,
                InterfaceIPv6.AUTO_ROUTES: True,
            },
        ),
    ],
    ids=["dhcpv4", "ipv6-ra", "dhcpv6", "dhcpv6+ra"],
)


class TestIPState:
    def test_discard_other_option_when_disabled(self):
        ip_state = IPState(
            Interface.IPV6, {InterfaceIPv6.ENABLED: False, "foo_a": "foo_b"}
        )
        assert ip_state.to_dict() == {
            InterfaceIP.ENABLED: False,
        }

    @parametrize_ip_ver
    def test_sort_address(self, ip_ver):
        family, ip_info = ip_ver
        ip_state1 = IPState(family, ip_info)
        ip_state1.sort_addresses()
        ip_info2 = deepcopy(ip_info)
        ip_info2[InterfaceIP.ADDRESS].reverse()
        ip_state2 = IPState(family, ip_info2)
        ip_state2.sort_addresses()
        assert ip_state1.to_dict() == ip_state2.to_dict()

    def test_ipv6_non_abbreviated_address(self):
        ip_state = IPState(
            Interface.IPV6,
            {
                InterfaceIPv6.ENABLED: True,
                InterfaceIPv6.ADDRESS: [
                    {
                        InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1_FULL,
                        InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                    }
                ],
            },
        )

        assert ip_state.to_dict() == {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: [
                {
                    InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            ],
        }

    @parametrize_ip_ver_dynamic
    def test_default_dynamic_options_when_undefined(self, ip_ver_dynamic):
        ip_info = {
            InterfaceIP.ENABLED: True,
        }
        family, dynamic_options = ip_ver_dynamic
        ip_info.update(dynamic_options)
        ip_info.pop(InterfaceIP.AUTO_DNS)
        ip_info.pop(InterfaceIP.AUTO_ROUTES)
        ip_info.pop(InterfaceIP.AUTO_GATEWAY)

        expected_ip_info = deepcopy(ip_info)
        expected_ip_info.update(dynamic_options)

        ip_state = IPState(family, ip_info)

        assert ip_state.to_dict() == expected_ip_info

    @parametrize_ip_ver_dynamic
    def test_discard_address_when_dynamic(self, ip_ver_dynamic):
        ip_info = {}
        family, dynamic_options = ip_ver_dynamic
        ip_info.update(dynamic_options)
        expected_ip_info = deepcopy(ip_info)
        ip_info[InterfaceIP.ADDRESS] = (
            IPV4_ADDRESSES if family == InterfaceIPv4 else IPV6_ADDRESSES
        )

        ip_state = IPState(family, ip_info)

        assert ip_state.to_dict() == expected_ip_info

    @parametrize_ip_ver
    def test_remove_link_local_address(self, ip_ver):
        family, ip_info = ip_ver
        expected_ip_info = deepcopy(ip_info)
        if family == Interface.IPV6:
            ip_info[InterfaceIPv6.ADDRESS].append(
                {
                    InterfaceIPv6.ADDRESS_IP: IPV6_LINK_LOCAL_ADDRESS1,
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            )

        ip_state = IPState(Interface.IPV6, ip_info)
        ip_state.remove_link_local_address()

        assert ip_state.to_dict() == expected_ip_info
