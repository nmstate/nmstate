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

from .common import NM
from .common import GLib


def create_ethtool_setting(iface_ethtool, base_con_profile):
    if not hasattr(NM, "ETHTOOL_OPTNAME_PAUSE_AUTONEG"):
        return None

    nm_setting = None

    if base_con_profile:
        nm_setting = base_con_profile.get_setting_by_name(
            NM.SETTING_ETHTOOL_SETTING_NAME
        )
        if nm_setting:
            nm_setting = nm_setting.duplicate()

    if not nm_setting:
        nm_setting = NM.SettingEthtool.new()

    if iface_ethtool.pause:
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

    return nm_setting
