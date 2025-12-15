# SPDX-License-Identifier: Apache-2.0

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
