# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2018-2019 Red Hat, Inc.
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

import ipaddress
from libnmstate.error import NmstateValueError

_IPV6_LINK_LOCAL_NETWORK_PREFIXES = ["fe8", "fe9", "fea", "feb"]
_IPV6_LINK_LOCAL_NETWORK_PREFIX_LENGTH = 10

KERNEL_MAIN_ROUTE_TABLE_ID = 254


def is_ipv6_link_local_addr(ip, prefix):
    return (
        ip[: len(_IPV6_LINK_LOCAL_NETWORK_PREFIXES[0])]
        in _IPV6_LINK_LOCAL_NETWORK_PREFIXES
        and prefix >= _IPV6_LINK_LOCAL_NETWORK_PREFIX_LENGTH
    )


def is_ipv6_address(addr):
    return ":" in addr


def to_ip_address_full(ip, prefix=None):
    if prefix:
        return f"{ip}/{prefix}"
    else:
        return to_ip_address_full(*ip_address_full_to_tuple(ip))


def ip_address_full_to_tuple(addr):
    try:
        net = ipaddress.ip_network(addr)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as err:
        raise NmstateValueError(f"Invalid IP address, error: {err}")

    return f"{net.network_address}", net.prefixlen


def canonicalize_ip_network(address):
    try:
        return ipaddress.ip_network(address, strict=False).with_prefixlen
    except ValueError as e:
        raise NmstateValueError(f"Invalid IP network address: {e}")


def canonicalize_ip_address(address):
    try:
        return ipaddress.ip_address(address).compressed
    except ValueError as e:
        raise NmstateValueError(f"Invalid IP address: {e}")
