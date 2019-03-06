#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
import ipaddress
import logging
import re
import six

_IPV6_LINK_LOCAL_NETWORK_PREFIXES = ['fe8', 'fe9', 'fea', 'feb']
_IPV6_LINK_LOCAL_NETWORK_PREFIX_LENGTH = 10

IPV4_LINK_LOCAL_NETWORK = "169.254.0.0/16"
IPV6_LINK_LOCAL_NETWORK = "fe80::/10"


def is_ipv6_link_local_addr(ip, prefix):
    return (ip[:len(_IPV6_LINK_LOCAL_NETWORK_PREFIXES[0])]
            in _IPV6_LINK_LOCAL_NETWORK_PREFIXES and
            prefix >= _IPV6_LINK_LOCAL_NETWORK_PREFIX_LENGTH)


def _is_subnet_of(a, b):
    """
    Copy from cpython 3.7 Lib/ipaddress.py file which is licensed under PSF,
    copyright 2007 Google Inc.
    """
    try:
        # Always false if one is v4 and the other is v6.
        if a._version != b._version:
            raise TypeError('{a} and {b} are not of the same version')
        return (b.network_address <= a.network_address and
                b.broadcast_address >= a.broadcast_address)
    except AttributeError:
        raise TypeError('Unable to test subnet containment '
                        'between {a} and {b}')


def is_subnet_of(network_a, network_b):
    """
    Check whether network_a is subnet of network_b.
    """
    a = ipaddress.ip_network(six.u(network_a), strict=False)
    b = ipaddress.ip_network(six.u(network_b), strict=False)
    if hasattr(a, 'subnet_of'):
        return a.subnet_of(b)
    else:
        return _is_subnet_of(a, b)


def get_route_table_name(table_id):
    """
    Parse /etc/iproute2/rt_tables to find out the route table name for given
    route table ID. Return empty string if not found or any error.
    """
    regex = re.compile('^[^#0-9]*{}\s+([^#]+)'.format(table_id))
    try:
        with open('/etc/iproute2/rt_tables') as fd:
            for line in fd:
                match = regex.match(line.strip())
                if match:
                    return match.groups()[0]
    except Exception as e:
        logging.debug(e)
    return ""


def get_route_table_id(table_name):
    """
    Parse /etc/iproute2/rt_tables to find out the route table ID for given
    route table name. Return 0 if not found or any error.
    """
    regex = re.compile('^[^#0-9]*([0-9]+)\s+{}[#\s]*$'.format(table_name))
    try:
        with open('/etc/iproute2/rt_tables') as fd:
            for line in fd:
                match = regex.match(line.strip())
                if match:
                    return int(match.groups()[0])
    except Exception as e:
        logging.debug(e)
    return 0
