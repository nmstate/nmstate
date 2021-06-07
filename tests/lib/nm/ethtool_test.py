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

import pytest
from unittest import mock

import libnmstate.nm.ethtool as nm_ethtool
from libnmstate.schema import Ethtool
from libnmstate.ifaces.ethtool import IfaceEthtool
from libnmstate.nm.common import GLib


@pytest.fixture
def nm_mock():
    with mock.patch.object(nm_ethtool, "NM") as m:
        yield m


def test_create_setting_pause_autoneg(nm_mock):
    iface_ethtool = IfaceEthtool(
        {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: True,
                Ethtool.Pause.RX: True,
                Ethtool.Pause.TX: True,
            }
        }
    )
    nm_ethtool_setting_mock = nm_mock.SettingEthtool.new.return_value

    nm_ethtool.create_ethtool_setting(iface_ethtool, base_con_profile=None)

    nm_ethtool_setting_mock.option_set.assert_has_calls(
        [
            mock.call(
                nm_mock.ETHTOOL_OPTNAME_PAUSE_AUTONEG,
                GLib.Variant.new_boolean(True),
            ),
            mock.call(nm_mock.ETHTOOL_OPTNAME_PAUSE_RX, None),
            mock.call(nm_mock.ETHTOOL_OPTNAME_PAUSE_TX, None),
        ],
        any_order=False,
    )


def test_create_setting_pause_autoneg_off(nm_mock):
    iface_ethtool = IfaceEthtool(
        {
            Ethtool.Pause.CONFIG_SUBTREE: {
                Ethtool.Pause.AUTO_NEGOTIATION: False,
                Ethtool.Pause.RX: True,
                Ethtool.Pause.TX: True,
            }
        }
    )
    nm_ethtool_setting_mock = nm_mock.SettingEthtool.new.return_value

    nm_ethtool.create_ethtool_setting(iface_ethtool, base_con_profile=None)

    nm_ethtool_setting_mock.option_set.assert_has_calls(
        [
            mock.call(
                nm_mock.ETHTOOL_OPTNAME_PAUSE_AUTONEG,
                GLib.Variant.new_boolean(False),
            ),
            mock.call(
                nm_mock.ETHTOOL_OPTNAME_PAUSE_RX,
                GLib.Variant.new_boolean(True),
            ),
            mock.call(
                nm_mock.ETHTOOL_OPTNAME_PAUSE_TX,
                GLib.Variant.new_boolean(True),
            ),
        ],
        any_order=False,
    )


def test_create_setting_ring(nm_mock):
    iface_ethtool = IfaceEthtool(
        {
            Ethtool.Ring.CONFIG_SUBTREE: {
                Ethtool.Ring.RX: 256,
                Ethtool.Ring.TX: 1024,
            }
        }
    )
    nm_ethtool_setting_mock = nm_mock.SettingEthtool.new.return_value

    nm_ethtool.create_ethtool_setting(iface_ethtool, base_con_profile=None)

    nm_ethtool_setting_mock.option_set.assert_has_calls(
        [
            mock.call(
                "ring-rx",
                GLib.Variant.new_uint32(256),
            ),
            mock.call(
                "ring-tx",
                GLib.Variant.new_uint32(1024),
            ),
        ],
        any_order=True,
    )


def test_create_setting_coalesce(nm_mock):
    iface_ethtool = IfaceEthtool(
        {
            Ethtool.Coalesce.CONFIG_SUBTREE: {
                Ethtool.Coalesce.ADAPTIVE_RX: True,
                Ethtool.Coalesce.ADAPTIVE_TX: False,
                Ethtool.Coalesce.RX_FRAMES: 100,
            }
        }
    )
    nm_ethtool_setting_mock = nm_mock.SettingEthtool.new.return_value

    nm_ethtool.create_ethtool_setting(iface_ethtool, base_con_profile=None)

    nm_ethtool_setting_mock.option_set.assert_has_calls(
        [
            mock.call(
                "coalesce-rx-frames",
                GLib.Variant.new_uint32(100),
            ),
            mock.call(
                "coalesce-adaptive-rx",
                GLib.Variant.new_uint32(1),
            ),
            mock.call(
                "coalesce-adaptive-tx",
                GLib.Variant.new_uint32(0),
            ),
        ],
        any_order=True,
    )
