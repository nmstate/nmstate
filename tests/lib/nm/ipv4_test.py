#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import pytest

from lib.compat import mock

from libnmstate import nm

IPV4_ADDRESS1 = '192.0.2.251'


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.ipv4.nmclient, 'NM') as m:
        yield m


def test_create_setting_without_config(NM_mock):
    ipv4_setting = nm.ipv4.create_setting(config=None, base_con_profile=None)

    assert ipv4_setting == NM_mock.SettingIP4Config.new.return_value
    assert (ipv4_setting.props.method ==
            NM_mock.SETTING_IP4_CONFIG_METHOD_DISABLED)


def test_create_setting_with_ipv4_disabled(NM_mock):
    ipv4_setting = nm.ipv4.create_setting(config={'enabled': False},
                                          base_con_profile=None)

    assert (ipv4_setting.props.method ==
            NM_mock.SETTING_IP4_CONFIG_METHOD_DISABLED)


def test_create_setting_without_addresses(NM_mock):
    ipv4_setting = nm.ipv4.create_setting(
        config={
            'enabled': True,
            'address': [],
        },
        base_con_profile=None
    )

    assert (ipv4_setting.props.method ==
            NM_mock.SETTING_IP4_CONFIG_METHOD_DISABLED)


def test_create_setting_with_static_addresses(NM_mock):
    config = {
        'enabled': True,
        'address': [
            {'ip': '10.10.10.1', 'prefix-length': 24},
            {'ip': '10.10.20.1', 'prefix-length': 24},
        ],
    }
    ipv4_setting = nm.ipv4.create_setting(config=config, base_con_profile=None)

    assert (ipv4_setting.props.method ==
            NM_mock.SETTING_IP4_CONFIG_METHOD_MANUAL)
    NM_mock.IPAddress.new.assert_has_calls(
        [
            mock.call(nm.ipv4.socket.AF_INET,
                      config['address'][0]['ip'],
                      config['address'][0]['prefix-length']),
            mock.call(nm.ipv4.socket.AF_INET,
                      config['address'][1]['ip'],
                      config['address'][1]['prefix-length'])
        ]
    )
    NM_mock.SettingIP4Config.new.return_value.add_address.assert_has_calls(
        [mock.call(NM_mock.IPAddress.new.return_value),
         mock.call(NM_mock.IPAddress.new.return_value)]
    )


def test_get_info_with_no_connection():
    info = nm.ipv4.get_info(active_connection=None)

    assert info == {'enabled': False}


def test_get_info_with_no_ipv4_config():
    con_mock = mock.MagicMock()
    con_mock.get_ip4_config.return_value = None

    info = nm.ipv4.get_info(active_connection=con_mock)

    assert info == {'enabled': False}


def test_get_info_with_ipv4_config():
    act_con_mock = mock.MagicMock()
    config_mock = act_con_mock.get_ip4_config.return_value
    address_mock = mock.MagicMock()
    config_mock.get_addresses.return_value = [address_mock]

    info = nm.ipv4.get_info(active_connection=act_con_mock)

    assert info == {
        'enabled': True,
        'address': [
            {
                'ip': address_mock.get_address.return_value,
                'prefix-length': int(address_mock.get_prefix.return_value),
            }
        ]
    }


def test_create_setting_with_base_con_profile(NM_mock):
    config = {
        'enabled': True,
        'address': [
            {'ip': IPV4_ADDRESS1, 'prefix-length': 24},
        ],
    }
    base_con_profile_mock = mock.MagicMock()
    config_mock = base_con_profile_mock.get_setting_ip4_config.return_value
    config_dup_mock = config_mock.duplicate.return_value

    nm.ipv4.create_setting(config=config,
                           base_con_profile=base_con_profile_mock)

    base_con_profile_mock.get_setting_ip4_config.assert_called_once_with()
    config_mock.duplicate.assert_called_once_with()
    config_dup_mock.clear_addresses.assert_called_once_with()
