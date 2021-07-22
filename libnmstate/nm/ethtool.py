#
# Copyright (c) 2018-2021 Red Hat, Inc.
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

from .common import NM
from .common import GLib

from libnmstate.ifaces import IfaceEthtool
from libnmstate.schema import Ethtool


_NM_RING_OPT_NAME_MAP = {
    Ethtool.Ring.RX: NM.ETHTOOL_OPTNAME_RING_RX,
    Ethtool.Ring.RX_JUMBO: NM.ETHTOOL_OPTNAME_RING_RX_JUMBO,
    Ethtool.Ring.RX_MINI: NM.ETHTOOL_OPTNAME_RING_RX_MINI,
    Ethtool.Ring.TX: NM.ETHTOOL_OPTNAME_RING_TX,
}

_EC = Ethtool.Coalesce
_NM_COALESCE_OPT_NAME_MAP = {
    _EC.ADAPTIVE_RX: NM.ETHTOOL_OPTNAME_COALESCE_ADAPTIVE_RX,
    _EC.ADAPTIVE_TX: NM.ETHTOOL_OPTNAME_COALESCE_ADAPTIVE_TX,
    _EC.PKT_RATE_HIGH: NM.ETHTOOL_OPTNAME_COALESCE_PKT_RATE_HIGH,
    _EC.PKT_RATE_LOW: NM.ETHTOOL_OPTNAME_COALESCE_PKT_RATE_LOW,
    _EC.RX_FRAMES: NM.ETHTOOL_OPTNAME_COALESCE_RX_FRAMES,
    _EC.RX_FRAMES_HIGH: NM.ETHTOOL_OPTNAME_COALESCE_RX_FRAMES_HIGH,
    _EC.RX_FRAMES_IRQ: NM.ETHTOOL_OPTNAME_COALESCE_RX_FRAMES_IRQ,
    _EC.RX_FRAMES_LOW: NM.ETHTOOL_OPTNAME_COALESCE_RX_FRAMES_LOW,
    _EC.RX_USECS: NM.ETHTOOL_OPTNAME_COALESCE_RX_USECS,
    _EC.RX_USECS_HIGH: NM.ETHTOOL_OPTNAME_COALESCE_RX_USECS_HIGH,
    _EC.RX_USECS_IRQ: NM.ETHTOOL_OPTNAME_COALESCE_RX_USECS_IRQ,
    _EC.RX_USECS_LOW: NM.ETHTOOL_OPTNAME_COALESCE_RX_USECS_LOW,
    _EC.SAMPLE_INTERVAL: NM.ETHTOOL_OPTNAME_COALESCE_SAMPLE_INTERVAL,
    _EC.STATS_BLOCK_USECS: NM.ETHTOOL_OPTNAME_COALESCE_STATS_BLOCK_USECS,
    _EC.TX_FRAMES: NM.ETHTOOL_OPTNAME_COALESCE_TX_FRAMES,
    _EC.TX_FRAMES_HIGH: NM.ETHTOOL_OPTNAME_COALESCE_TX_FRAMES_HIGH,
    _EC.TX_FRAMES_IRQ: NM.ETHTOOL_OPTNAME_COALESCE_TX_FRAMES_IRQ,
    _EC.TX_FRAMES_LOW: NM.ETHTOOL_OPTNAME_COALESCE_TX_FRAMES_LOW,
    _EC.TX_USECS: NM.ETHTOOL_OPTNAME_COALESCE_TX_USECS,
    _EC.TX_USECS_HIGH: NM.ETHTOOL_OPTNAME_COALESCE_TX_USECS_HIGH,
    _EC.TX_USECS_IRQ: NM.ETHTOOL_OPTNAME_COALESCE_TX_USECS_IRQ,
    _EC.TX_USECS_LOW: NM.ETHTOOL_OPTNAME_COALESCE_TX_USECS_LOW,
}


def _create_ethtool_setting(iface_ethtool, base_con_profile):
    nm_setting = None

    if base_con_profile:
        nm_setting = base_con_profile.get_setting_by_name(
            NM.SETTING_ETHTOOL_SETTING_NAME
        )
        if nm_setting:
            nm_setting = nm_setting.duplicate()

    if not nm_setting:
        nm_setting = NM.SettingEthtool.new()

    if iface_ethtool.pause and hasattr(NM, "ETHTOOL_OPTNAME_PAUSE_AUTONEG"):
        if iface_ethtool.pause.autoneg is True:
            nm_set_pause(nm_setting, True, None, None)
        elif iface_ethtool.pause.autoneg is False:
            nm_set_pause(
                nm_setting,
                False,
                iface_ethtool.pause.rx,
                iface_ethtool.pause.tx,
            )

    if iface_ethtool.feature:
        for kernel_feature_name, value in iface_ethtool.feature.items():
            nm_set_feature(nm_setting, kernel_feature_name, value)

    if iface_ethtool.ring:
        ring_info = iface_ethtool.ring.to_dict()
        for prop_name, nm_prop_name in _NM_RING_OPT_NAME_MAP.items():
            if prop_name in ring_info:
                nm_setting.option_set(
                    nm_prop_name,
                    GLib.Variant.new_uint32(ring_info[prop_name]),
                )

    if iface_ethtool.coalesce:
        coalesce_info = iface_ethtool.coalesce.to_dict()
        for prop_name, nm_prop_name in _NM_COALESCE_OPT_NAME_MAP.items():
            if prop_name in coalesce_info:
                value = coalesce_info[prop_name]
                if value is True:
                    value = 1
                elif value is False:
                    value = 0
                nm_setting.option_set(
                    nm_prop_name, GLib.Variant.new_uint32(value)
                )

    return nm_setting


_KERNEL_FEATURE_TO_NM_MAP = {
    "rx-checksum": "feature-rx",
    "tx-scatter-gather": "feature-sg",
    "tx-tcp-segmentation": "feature-tso",
    "rx-gro": "feature-gro",
    "tx-generic-segmentation": "feature-gso",
    "rx-hashing": "feature-rxhash",
    "rx-lro": "feature-lro",
    "rx-ntuple-filter": "feature-ntuple",
    "rx-vlan-hw-parse": "feature-rxvlan",
    "tx-vlan-hw-insert": "feature-txvlan",
}


def nm_set_feature(nm_setting, kernel_feature_name, value):
    """
    NM is using different name for some features.
    """
    nm_feature_name = _KERNEL_FEATURE_TO_NM_MAP.get(
        kernel_feature_name, f"feature-{kernel_feature_name}"
    )
    if NM.ethtool_optname_is_feature(nm_feature_name):
        nm_setting.option_set_boolean(nm_feature_name, value)
    else:
        logging.warning(
            f"Ethtool feature {kernel_feature_name} is invalid "
            "or not supported by current NetworkManager"
        )


def nm_set_pause(nm_setting, autoneg, rx, tx):
    rx_value = None if rx is None else GLib.Variant.new_boolean(rx)
    tx_value = None if tx is None else GLib.Variant.new_boolean(tx)
    # pylint: disable=no-member
    nm_setting.option_set(
        NM.ETHTOOL_OPTNAME_PAUSE_AUTONEG,
        GLib.Variant.new_boolean(autoneg),
    )
    nm_setting.option_set(
        NM.ETHTOOL_OPTNAME_PAUSE_RX,
        rx_value,
    )
    nm_setting.option_set(
        NM.ETHTOOL_OPTNAME_PAUSE_TX,
        tx_value,
    )
    # pylint: enable=no-member


def create_ethtool_setting(iface, base_con_profile):
    if Ethtool.CONFIG_SUBTREE in iface.original_desire_dict:
        iface_ethtool = IfaceEthtool(
            iface.original_desire_dict[Ethtool.CONFIG_SUBTREE]
        )
        iface_ethtool.canonicalize(
            iface.original_desire_dict[Ethtool.CONFIG_SUBTREE]
        )
        return _create_ethtool_setting(
            iface_ethtool,
            base_con_profile,
        )
    else:
        # Preserve existing setting but not create new
        if base_con_profile:
            ethtool_setting = base_con_profile.get_setting_by_name(
                NM.SETTING_ETHTOOL_SETTING_NAME
            )
            if ethtool_setting:
                return ethtool_setting.duplicate()
        return None
