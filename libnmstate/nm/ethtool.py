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

from libnmstate.error import NmstateValueError

from .common import NM
from .common import GLib


def create_ethtool_setting(iface_ethtool, base_con_profile):
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
        if iface_ethtool.pause.autoneg is not None:
            nm_setting.option_set(
                # pylint: disable=no-member
                NM.ETHTOOL_OPTNAME_PAUSE_AUTONEG,
                # pylint: enable=no-member
                GLib.Variant.new_boolean(iface_ethtool.pause.autoneg),
            )
        if iface_ethtool.pause.rx is not None:
            nm_setting.option_set(
                # pylint: disable=no-member
                NM.ETHTOOL_OPTNAME_PAUSE_RX,
                # pylint: enable=no-member
                GLib.Variant.new_boolean(iface_ethtool.pause.rx),
            )
        if iface_ethtool.pause.tx is not None:
            nm_setting.option_set(
                # pylint: disable=no-member
                NM.ETHTOOL_OPTNAME_PAUSE_TX,
                # pylint: enable=no-member
                GLib.Variant.new_boolean(iface_ethtool.pause.tx),
            )

    if iface_ethtool.feature:
        for kernel_feature_name, value in iface_ethtool.feature.items():
            nm_set_feature(nm_setting, kernel_feature_name, value)

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
        raise NmstateValueError(
            f"Ethtool feature {kernel_feature_name} is invalid "
            "or not supported by current NetworkManager"
        )
