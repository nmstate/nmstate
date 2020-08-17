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

import logging
from operator import attrgetter

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType


DEFAULT_MAC_ADDRESS = "00:00:00:00:00:00"


class NisporPluginBaseIface:
    def __init__(self, np_iface):
        self._np_iface = np_iface

    @property
    def np_iface(self):
        return self._np_iface

    @property
    def mac(self):
        mac = self._np_iface.mac_address
        if not mac:
            mac = DEFAULT_MAC_ADDRESS
        return mac

    @property
    def mtu(self):
        return self._np_iface.mtu

    @property
    def type(self):
        return InterfaceType.UNKNOWN

    @property
    def state(self):
        np_state = self._np_iface.state
        np_flags = self._np_iface.flags
        if np_state == "Up" or "Up" in np_flags or "Running" in np_flags:
            return InterfaceState.UP
        elif np_state == "Down":
            return InterfaceState.DOWN
        else:
            logging.debug(
                f"Got unexpect nispor interface state {np_state} for "
                f"{self._np_iface}"
            )
            return InterfaceState.DOWN

    def ip_info(self):
        return {
            Interface.IPV4: NisporPlugintIpState(
                Interface.IPV4, self.np_iface.ipv4
            ).to_dict(),
            Interface.IPV6: NisporPlugintIpState(
                Interface.IPV6, self.np_iface.ipv6
            ).to_dict(),
        }

    def to_dict(self):
        iface_info = {
            Interface.NAME: self.np_iface.name,
            Interface.TYPE: self.type,
            Interface.STATE: self.state,
            Interface.MAC: self.mac,
        }
        if self.mtu:
            iface_info[Interface.MTU] = self.mtu
        ip_info = self.ip_info()
        if ip_info:
            iface_info.update(ip_info)

        return iface_info


class NisporPlugintIpState:
    def __init__(self, family, np_ip_state):
        self._family = family
        self._np_ip_state = np_ip_state
        self._addresses = []
        if np_ip_state:
            self._addresses = sorted(
                np_ip_state.addresses, key=attrgetter("address")
            )

    @property
    def _is_ipv6(self):
        return self._family == Interface.IPV6

    def _has_dhcp_address(self):
        if self._is_ipv6:
            return any(
                addr.valid_lft != "forever" and addr.prefix_len == 128
                for addr in self._addresses
            )
        else:
            return any(addr.valid_lft != "forever" for addr in self._addresses)

    def _has_autoconf_address(self):
        return self._is_ipv6 and any(
            addr.valid_lft != "forever" and addr.prefix_len == 64
            for addr in self._addresses
        )

    def to_dict(self):
        if not self._addresses or not self._np_ip_state:
            return {InterfaceIP.ENABLED: False, InterfaceIP.ADDRESS: []}
        else:
            info = {
                InterfaceIP.ENABLED: True,
                InterfaceIP.ADDRESS: [
                    {
                        InterfaceIP.ADDRESS_IP: addr.address,
                        InterfaceIP.ADDRESS_PREFIX_LENGTH: addr.prefix_len,
                    }
                    for addr in self._addresses
                ],
            }
            if self._has_dhcp_address():
                info[InterfaceIP.DHCP] = True
            if self._has_autoconf_address():
                info[InterfaceIPv6.AUTOCONF] = True
            return info
