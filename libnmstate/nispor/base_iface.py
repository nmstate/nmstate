#
# Copyright (c) 2020-2021 Red Hat, Inc.
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

from libnmstate.ifaces import BaseIface
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Ethtool


DEFAULT_MAC_ADDRESS = "00:00:00:00:00:00"
PROMISC_FLAG = "promisc"


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

    @property
    def accept_all_mac_addresses(self):
        return PROMISC_FLAG in self._np_iface.flags

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
            Interface.ACCEPT_ALL_MAC_ADDRESSES: self.accept_all_mac_addresses,
        }
        if self._np_iface.permanent_mac_address:
            iface_info[
                BaseIface.PERMANENT_MAC_ADDRESS_METADATA
            ] = self._np_iface.permanent_mac_address
        elif (
            self._np_iface.controller_type == "bond"
            and self._np_iface.subordinate_state.perm_hwaddr
        ):
            # Bond port also hold perm_hwaddr which is the mac address before
            # this interface been assgined to bond as subordinate.
            iface_info[
                BaseIface.PERMANENT_MAC_ADDRESS_METADATA
            ] = self._np_iface.subordinate_state.perm_hwaddr
        if self.mtu:
            iface_info[Interface.MTU] = self.mtu
        ip_info = self._ip_info(config_only)
        if ip_info:
            iface_info.update(ip_info)
        if self.np_iface.ethtool:
            ethtool_info_dict = EthtoolInfo(self.np_iface.ethtool).to_dict()
            if ethtool_info_dict:
                iface_info[Ethtool.CONFIG_SUBTREE] = ethtool_info_dict

        if self.np_iface.controller:
            iface_info[Interface.CONTROLLER] = self.np_iface.controller
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


class EthtoolInfo:
    _NISPOR_COALESCE_OPT_NAME_MAP = {
        Ethtool.Coalesce.ADAPTIVE_RX: "use_adaptive_rx",
        Ethtool.Coalesce.ADAPTIVE_TX: "use_adaptive_tx",
        Ethtool.Coalesce.PKT_RATE_HIGH: "pkt_rate_high",
        Ethtool.Coalesce.PKT_RATE_LOW: "pkt_rate_low",
        Ethtool.Coalesce.RX_FRAMES: "rx_max_frames",
        Ethtool.Coalesce.RX_FRAMES_HIGH: "rx_max_frames_high",
        Ethtool.Coalesce.RX_FRAMES_IRQ: "rx_max_frames_irq",
        Ethtool.Coalesce.RX_FRAMES_LOW: "rx_max_frames_low",
        Ethtool.Coalesce.RX_USECS: "rx_usecs",
        Ethtool.Coalesce.RX_USECS_HIGH: "rx_usecs_high",
        Ethtool.Coalesce.RX_USECS_IRQ: "rx_usecs_irq",
        Ethtool.Coalesce.RX_USECS_LOW: "rx_usecs_low",
        Ethtool.Coalesce.SAMPLE_INTERVAL: "rate_sample_interval",
        Ethtool.Coalesce.STATS_BLOCK_USECS: "stats_block_usecs",
        Ethtool.Coalesce.TX_FRAMES: "tx_max_frames",
        Ethtool.Coalesce.TX_FRAMES_HIGH: "tx_max_frames_high",
        Ethtool.Coalesce.TX_FRAMES_IRQ: "tx_max_frames_irq",
        Ethtool.Coalesce.TX_FRAMES_LOW: "tx_max_frames_low",
        Ethtool.Coalesce.TX_USECS: "tx_usecs",
        Ethtool.Coalesce.TX_USECS_HIGH: "tx_usecs_high",
        Ethtool.Coalesce.TX_USECS_IRQ: "tx_usecs_irq",
        Ethtool.Coalesce.TX_USECS_LOW: "tx_usecs_low",
    }
    _NISPOR_ETHTOOL_FEATURE_SUPPORTED = [
        "rx-checksum",
        "tx-scatter-gather",
        "tx-tcp-segmentation",
        "rx-gro",
        "tx-generic-segmentation",
        "rx-hashing",
        "rx-lro",
        "rx-ntuple-filter",
        "rx-vlan-hw-parse",
        "tx-vlan-hw-insert",
        "highdma",
    ]

    def __init__(self, np_ethtool):
        self._np_ethtool = np_ethtool

    def to_dict(self):
        info = {}
        np_pause = self._np_ethtool.pause
        if np_pause:
            info[Ethtool.Pause.CONFIG_SUBTREE] = {
                Ethtool.Pause.AUTO_NEGOTIATION: np_pause.auto_negotiate,
                Ethtool.Pause.TX: np_pause.tx,
                Ethtool.Pause.RX: np_pause.rx,
            }
        np_features = self._np_ethtool.features
        if np_features:
            features = {}
            for (key, value) in np_features.changeable.items():
                if key in self._NISPOR_ETHTOOL_FEATURE_SUPPORTED:
                    features[key] = value
            info[Ethtool.Feature.CONFIG_SUBTREE] = features

        np_ring = self._np_ethtool.ring
        if np_ring:
            ring_info = {}
            if np_ring.tx is not None:
                ring_info[Ethtool.Ring.TX] = np_ring.tx

            if np_ring.rx is not None:
                ring_info[Ethtool.Ring.RX] = np_ring.rx

            if np_ring.rx_jumbo is not None:
                ring_info[Ethtool.Ring.RX_JUMBO] = np_ring.rx_jumbo

            if np_ring.rx_mini is not None:
                ring_info[Ethtool.Ring.RX_MINI] = np_ring.rx_mini

            if ring_info:
                info[Ethtool.Ring.CONFIG_SUBTREE] = ring_info
        np_coalesce = self._np_ethtool.coalesce
        if np_coalesce:
            coalesce_info = {}
            for (
                nmstate_name,
                nispor_name,
            ) in EthtoolInfo._NISPOR_COALESCE_OPT_NAME_MAP.items():
                if getattr(np_coalesce, nispor_name) is not None:
                    coalesce_info[nmstate_name] = getattr(
                        np_coalesce, nispor_name
                    )
            if coalesce_info:
                info[Ethtool.Coalesce.CONFIG_SUBTREE] = coalesce_info
        return info
