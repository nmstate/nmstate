#
# Copyright 2018-2019 Red Hat, Inc.
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

_IPV6_LINK_LOCAL_NETWORK_PREFIXES = ['fe8', 'fe9', 'fea', 'feb']
_IPV6_LINK_LOCAL_NETWORK_PREFIX_LENGTH = 10

KERNEL_MAIN_ROUTE_TABLE_ID = 254


def is_ipv6_link_local_addr(ip, prefix):
    return (ip[:len(_IPV6_LINK_LOCAL_NETWORK_PREFIXES[0])]
            in _IPV6_LINK_LOCAL_NETWORK_PREFIXES and
            prefix >= _IPV6_LINK_LOCAL_NETWORK_PREFIX_LENGTH)


def is_ipv6_address(addr):
    return ':' in addr
