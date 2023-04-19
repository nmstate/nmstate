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

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from libnmstate.ifaces.ifaces import Ifaces

from .constants import FOO_IFACE_NAME
from .constants import IPV4_ADDRESSES
from .constants import IPV6_ADDRESSES


def gen_foo_iface_info(iface_type=InterfaceType.ETHERNET):
    return {
        Interface.NAME: FOO_IFACE_NAME,
        Interface.TYPE: iface_type,
        Interface.STATE: InterfaceState.UP,
        Interface.IPV4: {InterfaceIPv4.ENABLED: False},
        Interface.IPV6: {InterfaceIPv6.ENABLED: False},
    }


def gen_foo_iface_info_static_ip(iface_type=InterfaceType.ETHERNET):
    iface_info = gen_foo_iface_info(iface_type)
    iface_info.update(
        {
            Interface.IPV4: {
                InterfaceIPv4.ENABLED: True,
                InterfaceIPv4.DHCP: False,
                InterfaceIPv4.ADDRESS: deepcopy(IPV4_ADDRESSES),
            },
            Interface.IPV6: {
                InterfaceIPv6.ENABLED: True,
                InterfaceIPv6.DHCP: False,
                InterfaceIPv6.ADDRESS: deepcopy(IPV6_ADDRESSES),
                InterfaceIPv6.AUTOCONF: False,
            },
        }
    )
    return iface_info


def gen_foo_iface_info_static_ip_only_ipv4(iface_type=InterfaceType.ETHERNET):
    iface_info = gen_foo_iface_info(iface_type)
    iface_info.update(
        {
            Interface.IPV4: {
                InterfaceIPv4.ENABLED: True,
                InterfaceIPv4.DHCP: False,
                InterfaceIPv4.ADDRESS: deepcopy(IPV4_ADDRESSES),
            },
        }
    )
    return iface_info


def gen_two_static_ip_ifaces(iface1_name, iface2_name):
    iface1_info = gen_foo_iface_info_static_ip()
    iface1_info[Interface.NAME] = iface1_name
    iface1_info[Interface.IPV4][InterfaceIPv4.ADDRESS].pop(1)
    iface1_info[Interface.IPV6][InterfaceIPv6.ADDRESS].pop(1)
    iface2_info = gen_foo_iface_info_static_ip()
    iface2_info[Interface.NAME] = iface2_name
    iface2_info[Interface.IPV4][InterfaceIPv4.ADDRESS].pop(0)
    iface2_info[Interface.IPV6][InterfaceIPv6.ADDRESS].pop(0)
    return Ifaces([], [iface1_info, iface2_info])


def gen_two_static_ip_ifaces_different(iface1_name, iface2_name):
    iface1_info = gen_foo_iface_info_static_ip_only_ipv4()
    iface1_info[Interface.NAME] = iface1_name
    iface1_info[Interface.IPV4][InterfaceIPv4.ADDRESS].pop(1)
    iface2_info = gen_foo_iface_info_static_ip()
    iface2_info[Interface.NAME] = iface2_name
    iface2_info[Interface.IPV4][InterfaceIPv4.ADDRESS].pop(0)
    iface2_info[Interface.IPV6][InterfaceIPv6.ADDRESS].pop(0)
    return Ifaces([], [iface1_info, iface2_info])
