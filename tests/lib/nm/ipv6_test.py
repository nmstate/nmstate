#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

from libnmstate import nm
from libnmstate.schema import InterfaceIPv6

# IPv6 Address Prefix Reserved for Documentation:
# https://tools.ietf.org/html/rfc3849
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_LINK_LOCAL_ADDRESS1 = "fe80::1"


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.ipv6, "NM") as m:
        yield m


def test_create_setting_without_config(NM_mock):
    NM_mock.SettingIP6Config.new().props.addresses = []
    NM_mock.NM.SETTING_IP6_CONFIG_METHOD_DISABLED = "disabled"

    ipv6_setting = nm.ipv6.create_setting(config=None, base_con_profile=None)

    assert ipv6_setting == NM_mock.SettingIP6Config.new.return_value
    disable_method = NM_mock.SETTING_IP6_CONFIG_METHOD_DISABLED
    assert ipv6_setting.props.method == disable_method


def test_create_setting_with_ipv6_disabled(NM_mock):
    NM_mock.SettingIP6Config.new().props.addresses = []
    NM_mock.NM.SETTING_IP6_CONFIG_METHOD_DISABLED = "disabled"

    ipv6_setting = nm.ipv6.create_setting(
        config={InterfaceIPv6.ENABLED: False}, base_con_profile=None
    )

    assert ipv6_setting == NM_mock.SettingIP6Config.new.return_value
    disable_method = NM_mock.SETTING_IP6_CONFIG_METHOD_DISABLED

    assert ipv6_setting.props.method == disable_method


def test_create_setting_without_addresses(NM_mock):
    NM_mock.SettingIP6Config.new().props.addresses = []

    ipv6_setting = nm.ipv6.create_setting(
        config={InterfaceIPv6.ENABLED: True, InterfaceIPv6.ADDRESS: []},
        base_con_profile=None,
    )

    assert (
        ipv6_setting.props.method
        == NM_mock.SETTING_IP6_CONFIG_METHOD_LINK_LOCAL
    )


def test_create_setting_with_static_addresses(NM_mock):
    config = {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: "fd12:3456:789a:1::1",
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 24,
            },
            {
                InterfaceIPv6.ADDRESS_IP: "fd12:3456:789a:2::1",
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 24,
            },
        ],
    }
    ipv6_setting = nm.ipv6.create_setting(config=config, base_con_profile=None)

    assert (
        ipv6_setting.props.method == NM_mock.SETTING_IP6_CONFIG_METHOD_MANUAL
    )
    NM_mock.IPAddress.new.assert_has_calls(
        [
            mock.call(
                nm.ipv6.socket.AF_INET6,
                config[InterfaceIPv6.ADDRESS][0][InterfaceIPv6.ADDRESS_IP],
                config[InterfaceIPv6.ADDRESS][0][
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH
                ],
            ),
            mock.call(
                nm.ipv6.socket.AF_INET6,
                config[InterfaceIPv6.ADDRESS][1][InterfaceIPv6.ADDRESS_IP],
                config[InterfaceIPv6.ADDRESS][1][
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH
                ],
            ),
        ]
    )
    NM_mock.SettingIP6Config.new.return_value.add_address.assert_has_calls(
        [
            mock.call(NM_mock.IPAddress.new.return_value),
            mock.call(NM_mock.IPAddress.new.return_value),
        ]
    )


def test_get_info_with_no_connection():
    info = nm.ipv6.get_info(active_connection=None, applied_config=None)

    assert info == {}


def test_get_info_with_no_applied_config():
    con_mock = mock.MagicMock()

    info = nm.ipv6.get_info(active_connection=con_mock, applied_config=None)

    assert info == {}


def test_get_info_with_no_ip_profile():
    con_mock = mock.MagicMock()
    applied_config_mock = mock.MagicMock()
    applied_config_mock.get_setting_ip6_config.return_value = None

    info = nm.ipv6.get_info(
        active_connection=con_mock, applied_config=applied_config_mock
    )

    assert info == {
        InterfaceIPv6.ENABLED: False,
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.AUTOCONF: False,
    }


def test_get_info_with_ip_profile(NM_mock):
    act_con_mock = mock.MagicMock()
    applied_config_mock = mock.MagicMock()
    ip_profile = mock.MagicMock()
    applied_config_mock.get_setting_ip6_config.return_value = ip_profile
    ip_profile.get_method.return_value = (
        NM_mock.SETTING_IP6_CONFIG_METHOD_MANUAL
    )
    ip_profile.props.never_default = False
    ip_profile.props.ignore_auto_dns = False
    ip_profile.props.ignore_auto_routes = False

    info = nm.ipv6.get_info(
        active_connection=act_con_mock, applied_config=applied_config_mock
    )

    assert info == {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.DHCP: False,
        InterfaceIPv6.AUTOCONF: False,
    }


def test_create_setting_with_link_local_addresses(NM_mock):
    config = {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_LINK_LOCAL_ADDRESS1,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            },
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            },
        ],
    }
    ipv6_setting = nm.ipv6.create_setting(config=config, base_con_profile=None)

    assert (
        ipv6_setting.props.method == NM_mock.SETTING_IP6_CONFIG_METHOD_MANUAL
    )
    NM_mock.IPAddress.new.assert_has_calls(
        [
            mock.call(
                nm.ipv6.socket.AF_INET6,
                config[InterfaceIPv6.ADDRESS][1][InterfaceIPv6.ADDRESS_IP],
                config[InterfaceIPv6.ADDRESS][1][
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH
                ],
            )
        ]
    )
    NM_mock.SettingIP6Config.new.return_value.add_address.assert_has_calls(
        [mock.call(NM_mock.IPAddress.new.return_value)]
    )


def test_create_setting_with_base_con_profile(NM_mock):
    config = {
        InterfaceIPv6.ENABLED: True,
        InterfaceIPv6.ADDRESS: [
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
    }
    base_con_profile_mock = mock.MagicMock()
    config_mock = base_con_profile_mock.get_setting_ip6_config.return_value
    config_dup_mock = config_mock.duplicate.return_value

    nm.ipv6.create_setting(
        config=config, base_con_profile=base_con_profile_mock
    )

    base_con_profile_mock.get_setting_ip6_config.assert_called_once_with()
    config_mock.duplicate.assert_called_once_with()
    config_dup_mock.clear_addresses.assert_called_once_with()
