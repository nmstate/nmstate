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

from libnmstate.schema import InterfaceIP

FOO_IFACE_NAME = "foo"
MAC_ADDRESS1 = "01:23:45:67:89:AB"
MAC_ADDRESS2 = "01:23:45:67:89:AC"

IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS1_FULL = "2001:db8:1:0:0:0:0:1"
IPV6_ADDRESS2 = "2001:db8:2::1"
IPV6_ADDRESS3 = "2001:db8:3::1"
IPV6_LINK_LOCAL_ADDRESS1 = "fe80::1"
IPV6_ADDRESSES = [
    {
        InterfaceIP.ADDRESS_IP: IPV6_ADDRESS1,
        InterfaceIP.ADDRESS_PREFIX_LENGTH: 64,
    },
    {
        InterfaceIP.ADDRESS_IP: IPV6_ADDRESS2,
        InterfaceIP.ADDRESS_PREFIX_LENGTH: 64,
    },
]

IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV4_ADDRESS3 = "192.0.2.253"
IPV4_ADDRESSES = [
    {
        InterfaceIP.ADDRESS_IP: IPV4_ADDRESS1,
        InterfaceIP.ADDRESS_PREFIX_LENGTH: 24,
    },
    {
        InterfaceIP.ADDRESS_IP: IPV4_ADDRESS2,
        InterfaceIP.ADDRESS_PREFIX_LENGTH: 24,
    },
]

PORT1_IFACE_NAME = "port1"
PORT2_IFACE_NAME = "port2"
