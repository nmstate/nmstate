#
# Copyright (c) 2019 Red Hat, Inc.
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
from .testlib import context


TEST_IFACE = "eth1"

IPV4_ADDRESS1 = "192.0.2.251"


@iproutelib.ip_monitor_assert_stable_link_up(TEST_IFACE)
def test_interface_ipv4_change(eth1_up):
    with context() as ctx:
        _modify_interface(
            ctx,
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

    with context() as ctx:
        ipv4_current_state = _get_ipv4_current_state(ctx, TEST_IFACE)

    ip4_expected_state = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.DHCP: False,
        InterfaceIPv4.ADDRESS: [
            {
                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        ],
    }
    assert ip4_expected_state == ipv4_current_state


def test_enable_dhcp_with_no_server(eth1_up):
    with context() as ctx:
        _modify_interface(
            ctx,
            ipv4_state={
                InterfaceIPv4.ENABLED: True,
                InterfaceIPv4.DHCP: True,
                InterfaceIPv4.ADDRESS: [],
            },
        )

    with context() as ctx:
        ipv4_current_state = _get_ipv4_current_state(ctx, TEST_IFACE)

    expected_ipv4_state = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.DHCP: True,
        InterfaceIPv4.ADDRESS: [],
        InterfaceIPv4.AUTO_DNS: True,
        InterfaceIPv4.AUTO_GATEWAY: True,
        InterfaceIPv4.AUTO_ROUTES: True,
    }
    assert ipv4_current_state == expected_ipv4_state


def _modify_interface(ctx, ipv4_state):
    conn = nm.connection.ConnectionProfile(ctx)
    conn.import_by_id(TEST_IFACE)
    settings = _create_iface_settings(ctx, ipv4_state, conn)
    new_conn = nm.connection.ConnectionProfile(ctx)
    new_conn.create(settings)
    conn.update(new_conn)
    conn.commit(save_to_disk=False)

    nmdev = nm.device.get_device_by_name(ctx, TEST_IFACE)
    nm.device.reapply(ctx, nmdev, conn.profile)


def _get_ipv4_current_state(ctx, ifname):
    nmdev = nm.device.get_device_by_name(ctx, ifname)
    active_connection = nm.connection.get_device_active_connection(nmdev)
    return nm.ipv4.get_info(ctx, active_connection)


def _create_iface_settings(ctx, ipv4_state, con_profile):
    con_setting = nm.connection.ConnectionSetting(ctx)
    con_setting.import_by_profile(con_profile)

    # Wired is required due to https://bugzilla.redhat.com/1703960
    wired_setting = con_profile.profile.get_setting_wired()

    ipv4_setting = nm.ipv4.create_setting(ctx, ipv4_state, con_profile.profile)
    ipv6_setting = nm.ipv6.create_setting(ctx, {}, None)

    return con_setting.setting, wired_setting, ipv4_setting, ipv6_setting
