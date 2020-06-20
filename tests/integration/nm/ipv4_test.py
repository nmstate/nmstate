#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from libnmstate import nm
from libnmstate.schema import InterfaceIPv4

from ..testlib import iproutelib
from ..testlib.retry import retry_till_true_or_timeout
from .testlib import main_context


TEST_IFACE = "eth1"

IPV4_ADDRESS1 = "192.0.2.251"

RETRY_TIMEOUT = 5


def _ip_state_is_expected(nm_plugin, expected_state):
    nm_plugin.refresh_content()
    ipv4_current_state = _get_ipv4_current_state(nm_plugin.context, TEST_IFACE)
    return ipv4_current_state == expected_state


@iproutelib.ip_monitor_assert_stable_link_up(TEST_IFACE)
def test_interface_ipv4_change(eth1_up, nm_plugin):
    _modify_interface(
        nm_plugin.context,
        ipv4_state={
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        },
    )

    expected_ipv4_state = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.DHCP: False,
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
    }
    assert retry_till_true_or_timeout(
        RETRY_TIMEOUT, _ip_state_is_expected, nm_plugin, expected_ipv4_state
    )


def test_enable_dhcp_with_no_server(eth1_up, nm_plugin):
    _modify_interface(
        nm_plugin.context,
        ipv4_state={
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: True,
            InterfaceIPv4.ADDRESS: [],
        },
    )

    expected_ipv4_state = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.DHCP: True,
        InterfaceIPv4.ADDRESS: [],
        InterfaceIPv4.AUTO_DNS: True,
        InterfaceIPv4.AUTO_GATEWAY: True,
        InterfaceIPv4.AUTO_ROUTES: True,
        InterfaceIPv4.AUTO_ROUTE_TABLE_ID: 0,
    }
    assert retry_till_true_or_timeout(
        RETRY_TIMEOUT, _ip_state_is_expected, nm_plugin, expected_ipv4_state
    )


def _modify_interface(ctx, ipv4_state):
    conn = nm.connection.ConnectionProfile(ctx)
    conn.import_by_id(TEST_IFACE)
    settings = _create_iface_settings(ipv4_state, conn)
    new_conn = nm.connection.ConnectionProfile(ctx)
    new_conn.create(settings)
    with main_context(ctx):
        conn.update(new_conn)
        ctx.wait_all_finish()
        nmdev = ctx.get_nm_dev(TEST_IFACE)
        nm.device.modify(ctx, nmdev, new_conn.profile)


def _get_ipv4_current_state(ctx, ifname):
    nmdev = ctx.get_nm_dev(ifname)
    active_connection = nm.connection.get_device_active_connection(nmdev)
    return nm.ipv4.get_info(active_connection)


def _create_iface_settings(ipv4_state, con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(con_profile)

    ipv4_setting = nm.ipv4.create_setting(ipv4_state, con_profile.profile)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    return con_setting.setting, ipv4_setting, ipv6_setting
