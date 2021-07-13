#
# Copyright (c) 2021 Red Hat, Inc.
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
import logging

from libnmstate.schema import Ethtool
from libnmstate.validator import validate_boolean
from libnmstate.validator import validate_integer


ETHTOOL_COALESCE_INTEGER = [
    Ethtool.Coalesce.PKT_RATE_HIGH,
    Ethtool.Coalesce.PKT_RATE_LOW,
    Ethtool.Coalesce.RX_FRAMES,
    Ethtool.Coalesce.RX_FRAMES_HIGH,
    Ethtool.Coalesce.RX_FRAMES_IRQ,
    Ethtool.Coalesce.RX_FRAMES_LOW,
    Ethtool.Coalesce.RX_USECS,
    Ethtool.Coalesce.RX_USECS_HIGH,
    Ethtool.Coalesce.RX_USECS_IRQ,
    Ethtool.Coalesce.RX_USECS_LOW,
    Ethtool.Coalesce.SAMPLE_INTERVAL,
    Ethtool.Coalesce.STATS_BLOCK_USECS,
    Ethtool.Coalesce.TX_FRAMES,
    Ethtool.Coalesce.TX_FRAMES_HIGH,
    Ethtool.Coalesce.TX_FRAMES_IRQ,
    Ethtool.Coalesce.TX_FRAMES_LOW,
    Ethtool.Coalesce.TX_USECS,
    Ethtool.Coalesce.TX_USECS_HIGH,
    Ethtool.Coalesce.TX_USECS_IRQ,
    Ethtool.Coalesce.TX_USECS_LOW,
]


class IfaceEthtool:
    def __init__(self, ethtool_info):
        self._info = ethtool_info
        self._pause = None
        if self._info.get(Ethtool.Pause.CONFIG_SUBTREE):
            self._pause = IfaceEthtoolPause(
                self._info[Ethtool.Pause.CONFIG_SUBTREE]
            )
        self._feature = None
        if self._info.get(Ethtool.Feature.CONFIG_SUBTREE):
            self._feature = IfaceEthtoolFeature(
                self._info[Ethtool.Feature.CONFIG_SUBTREE]
            )
        self._ring = None
        if self._info.get(Ethtool.Ring.CONFIG_SUBTREE):
            self._ring = IfaceEthtoolRing(
                self._info[Ethtool.Ring.CONFIG_SUBTREE]
            )
        self._coalesce = None
        if self._info.get(Ethtool.Coalesce.CONFIG_SUBTREE):
            self._coalesce = IfaceEthtoolCoalesce(
                self._info[Ethtool.Coalesce.CONFIG_SUBTREE]
            )

    @property
    def pause(self):
        return self._pause

    @property
    def feature(self):
        return self._feature

    @property
    def ring(self):
        return self._ring

    @property
    def coalesce(self):
        return self._coalesce

    def canonicalize(self, original_desire):
        if self.pause:
            self.pause.canonicalize(
                original_desire.get(Ethtool.Pause.CONFIG_SUBTREE, {})
            )
        if self.feature:
            self.feature.canonicalize(
                original_desire.get(Ethtool.Feature.CONFIG_SUBTREE, {})
            )
        if self.ring:
            self.ring.canonicalize(
                original_desire.get(Ethtool.Ring.CONFIG_SUBTREE, {})
            )
        if self.coalesce:
            self.coalesce.canonicalize(
                original_desire.get(Ethtool.Coalesce.CONFIG_SUBTREE, {})
            )

    def to_dict(self):
        info = {}
        if self.pause:
            info[Ethtool.Pause.CONFIG_SUBTREE] = self.pause.to_dict()
        if self.feature:
            info[Ethtool.Feature.CONFIG_SUBTREE] = self.feature.to_dict()
        if self.ring:
            info[Ethtool.Ring.CONFIG_SUBTREE] = self.ring.to_dict()
        if self.coalesce:
            info[Ethtool.Coalesce.CONFIG_SUBTREE] = self.coalesce.to_dict()
        return info

    def pre_edit_validation_and_cleanup(self):
        self._validate_ethtool_properties()

    def _validate_ethtool_properties(self):
        if self.pause:
            validate_boolean(
                self.pause.autoneg, Ethtool.Pause.AUTO_NEGOTIATION
            )
            validate_boolean(self.pause.rx, Ethtool.Pause.RX)
            validate_boolean(self.pause.tx, Ethtool.Pause.TX)
        if self.ring:
            validate_integer(
                self.ring.to_dict().get(Ethtool.Ring.TX),
                Ethtool.Ring.TX,
                minimum=0,
            )
            validate_integer(
                self.ring.to_dict().get(Ethtool.Ring.RX),
                Ethtool.Ring.RX,
                minimum=0,
            )
            validate_integer(
                self.ring.to_dict().get(Ethtool.Ring.RX_JUMBO),
                Ethtool.Ring.RX_JUMBO,
                minimum=0,
            )
            validate_integer(
                self.ring.to_dict().get(Ethtool.Ring.RX_MINI),
                Ethtool.Ring.RX_MINI,
                minimum=0,
            )
        if self.coalesce:
            validate_boolean(
                self.coalesce.to_dict().get(Ethtool.Coalesce.ADAPTIVE_RX),
                Ethtool.Coalesce.ADAPTIVE_RX,
            )
            validate_boolean(
                self.coalesce.to_dict().get(Ethtool.Coalesce.ADAPTIVE_TX),
                Ethtool.Coalesce.ADAPTIVE_TX,
            )
            for coalesce_prop in ETHTOOL_COALESCE_INTEGER:
                validate_integer(
                    self.coalesce.to_dict().get(coalesce_prop),
                    coalesce_prop,
                    minimum=0,
                )


class IfaceEthtoolPause:
    def __init__(self, pause_info):
        self._info = pause_info

    @property
    def autoneg(self):
        return self._info.get(Ethtool.Pause.AUTO_NEGOTIATION)

    @property
    def rx(self):
        return self._info.get(Ethtool.Pause.RX)

    @property
    def tx(self):
        return self._info.get(Ethtool.Pause.TX)

    def canonicalize(self, original_desire):
        """
        When AUTO_NEGOTIATION is enabled, RX and TX should be ignored.
        Log warnning if desired has AUTO_NEGOTIATION: True and RX/TX
        configured.
        Remove RX/TX when AUTO_NEGOTIATION is enabled.
        """
        if self.autoneg and (
            original_desire.get(Ethtool.Pause.RX) is not None
            or original_desire.get(Ethtool.Pause.TX) is not None
        ):
            logging.warn(
                "Ignoring RX/TX configure of ethtool PAUSE when "
                "AUTO_NEGOTIATION enabled"
            )
        if self.autoneg:
            self._info.pop(Ethtool.Pause.RX, None)
            self._info.pop(Ethtool.Pause.TX, None)

    def to_dict(self):
        return deepcopy(self._info)


class IfaceEthtoolFeature:
    _ETHTOOL_CLI_ALIASES = {
        "rx": "rx-checksum",
        "rx-checksumming": "rx-checksum",
        "ufo": "tx-udp-fragmentation",
        "gso": "tx-generic-segmentation",
        "generic-segmentation-offload": "tx-generic-segmentation",
        "gro": "rx-gro",
        "generic-receive-offload": "rx-gro",
        "lro": "rx-lro",
        "large-receive-offload": "rx-lro",
        "rxvlan": "rx-vlan-hw-parse",
        "rx-vlan-offload": "rx-vlan-hw-parse",
        "txvlan": "tx-vlan-hw-insert",
        "tx-vlan-offload": "tx-vlan-hw-insert",
        "ntuple": "rx-ntuple-filter",
        "ntuple-filters": "rx-ntuple-filter",
        "rxhash": "rx-hashing",
        "receive-hashing": "rx-hashing",
    }

    def __init__(self, feature_info):
        self._info = feature_info

    def canonicalize(self, original_desire):
        """
        * Convert ethtool CLI alias to kernel names both in self and
        original_desire
        """
        saved_keys = list(self._info.keys())
        for key in saved_keys:
            if key in IfaceEthtoolFeature._ETHTOOL_CLI_ALIASES:
                kernel_key_name = IfaceEthtoolFeature._ETHTOOL_CLI_ALIASES[key]
                self._info[kernel_key_name] = self._info[key]
                original_desire[kernel_key_name] = self._info[key]
                self._info.pop(key)
                original_desire.pop(key, None)

    def items(self):
        for k, v in self._info.items():
            yield k, v

    def to_dict(self):
        return deepcopy(self._info)


class IfaceEthtoolRing:
    def __init__(self, ring_info):
        self._info = ring_info

    def canonicalize(self, _original_desire):
        pass

    def to_dict(self):
        return deepcopy(self._info)


class IfaceEthtoolCoalesce:
    def __init__(self, coalesce_info):
        self._info = coalesce_info

    def canonicalize(self, _original_desire):
        pass

    def to_dict(self):
        return deepcopy(self._info)
