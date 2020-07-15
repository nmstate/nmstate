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

from operator import itemgetter

from libnmstate.error import NmstateInternalError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState


class NisporBaseIface:
    def __init__(self, np_info):
        self._np_info = np_info

    @property
    def np_info(self):
        return self._np_info

    @property
    def mac(self):
        return self._np_info.get("mac_address", "00:00:00:00:00:00")

    @property
    def mtu(self):
        return self._np_info["mtu"]

    @property
    def state(self):
        np_info = self._np_info["state"]
        # Subordinate port like bridge port might in down link state at certain
        # point(e.g. bridge STP)
        if np_info == "Up" or self._is_subordinate:
            return InterfaceState.UP
        elif np_info == "Down":
            return InterfaceState.DOWN
        else:
            raise NmstateInternalError(
                f"Got unexpect nispor interface state {np_info} for "
                f"{self._np_info}"
            )

    @property
    def _is_subordinate(self):
        return "bridge_port" in self.np_info or "bond_slave" in self.np_info

    @property
    def ip_info(self):
        return {
            Interface.IPV4: NisportIpState(
                Interface.IPV4, self.np_info.get("ipv4")
            ).to_dict(),
            Interface.IPV6: NisportIpState(
                Interface.IPV6, self.np_info.get("ipv6")
            ).to_dict(),
        }

    def to_dict(self):
        iface_info = {
            Interface.NAME: self.np_info["name"],
            Interface.STATE: self.state,
            Interface.MAC: self.mac,
            Interface.MTU: self.mtu,
        }
        if self.state == InterfaceState.UP:
            iface_info.update(self.ip_info)

        return iface_info


class NisportIpState:
    def __init__(self, family, np_info):
        self._family = family
        self._np_info = np_info
        self._addresses = []
        if np_info:
            self._addresses = sorted(np_info.get("addresses", []),
                    key=itemgetter("address"))

    @property
    def _is_ipv6(self):
        return self._family == Interface.IPV6

    def _has_dhcp_address(self):
        if self._is_ipv6:
            return any(
                addr["valid_lft"] != "forever" and addr["prefix_len"] == 128
                for addr in self._addresses
            )
        else:
            return any(
                addr["valid_lft"] != "forever" for addr in self._addresses
            )

    def _has_autoconf_address(self):
        return self._is_ipv6 and any(
            addr["valid_lft"] != "forever" and addr["prefix_len"] == 64
            for addr in self._addresses
        )

    def to_dict(self):
        if not self._addresses or not self._np_info:
            if self._is_ipv6:
                # IPv6 is considered as disabled if there is no even
                # IPv6 link local address
                return {
                    InterfaceIP.ENABLED: False,
                }
            else:
                # When there is not IPv4 address, we don't know whether
                # interface is disabled or not just waiting DHCP,
                # let other plugin discover the enable status
                return {}
        else:
            info = {
                InterfaceIP.ENABLED: True,
                InterfaceIP.ADDRESS: [
                    {
                        InterfaceIP.ADDRESS_IP: addr["address"],
                        InterfaceIP.ADDRESS_PREFIX_LENGTH: addr["prefix_len"],
                    }
                    for addr in self._addresses
                ],
            }
            if self._has_dhcp_address():
                info[InterfaceIP.DHCP] = True
            if self._has_autoconf_address():
                info[InterfaceIPv6.AUTOCONF] = True
            return info
