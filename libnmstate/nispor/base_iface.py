# SPDX-License-Identifier: LGPL-2.1-or-later

import logging

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
        if self._np_iface.mac_address:
            return self._np_iface.mac_address.upper()
        return DEFAULT_MAC_ADDRESS

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
        if np_state == "up" or "up" in np_flags or "running" in np_flags:
            return InterfaceState.UP
        elif np_state == "down":
            return InterfaceState.DOWN
        else:
            logging.debug(
                f"Got unexpect nispor interface state {np_state} for "
                f"{self._np_iface}"
            )
            return InterfaceState.DOWN

    def _ip_info(self, config_only):
        return {
            Interface.IPV4: NisporPlugintIpState(
                Interface.IPV4, self.np_iface.ipv4
            ).to_dict(config_only),
            Interface.IPV6: NisporPlugintIpState(
                Interface.IPV6, self.np_iface.ipv6
            ).to_dict(config_only),
        }

    def to_dict(self, config_only):
        iface_info = {
            Interface.NAME: self.np_iface.name,
            Interface.TYPE: self.type,
            Interface.STATE: self.state,
            Interface.MAC: self.mac,
        }
        if self.mtu:
            iface_info[Interface.MTU] = self.mtu
        ip_info = self._ip_info(config_only)
        if ip_info:
            iface_info.update(ip_info)

        return iface_info


class NisporPlugintIpState:
    def __init__(self, family, np_ip_state):
        self._family = family
        self._np_ip_state = np_ip_state
        self._addresses = []
        if np_ip_state:
            self._addresses = np_ip_state.addresses

    @property
    def _is_ipv6(self):
        return self._family == Interface.IPV6

    def _has_dhcp_address(self):
        return any(
            _is_dhcp_addr(addr, self._is_ipv6) for addr in self._addresses
        )

    def _has_autoconf_address(self):
        return self._is_ipv6 and any(
            _is_autoconf_addr(addr) for addr in self._addresses
        )

    def to_dict(self, config_only):
        if not self._addresses or not self._np_ip_state:
            return {InterfaceIP.ENABLED: False, InterfaceIP.ADDRESS: []}
        else:
            if config_only:
                addresses = [
                    addr
                    for addr in self._addresses
                    if not _is_autoconf_addr(addr)
                    and not _is_dhcp_addr(addr, self._is_ipv6)
                ]
            else:
                addresses = self._addresses
            info = {
                InterfaceIP.ENABLED: True,
                InterfaceIP.ADDRESS: [
                    {
                        InterfaceIP.ADDRESS_IP: addr.address,
                        InterfaceIP.ADDRESS_PREFIX_LENGTH: addr.prefix_len,
                    }
                    for addr in addresses
                ],
            }
            if self._has_dhcp_address():
                info[InterfaceIP.DHCP] = True
            if self._has_autoconf_address():
                info[InterfaceIPv6.AUTOCONF] = True
            return info


def _is_dhcp_addr(np_addr, is_ipv6):
    if is_ipv6:
        return np_addr.valid_lft != "forever" and np_addr.prefix_len == 128
    else:
        return np_addr.valid_lft != "forever"


def _is_autoconf_addr(np_addr):
    return np_addr.valid_lft != "forever" and np_addr.prefix_len == 64
