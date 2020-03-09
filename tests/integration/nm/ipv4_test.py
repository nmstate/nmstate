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
from libnmstate.nm.nmclient import nmclient_context
from libnmstate.schema import InterfaceIPv4

from ..testlib import iproutelib
from .testlib import mainloop_run


TEST_IFACE = "eth1"

IPV4_ADDRESS1 = "192.0.2.251"


@iproutelib.ip_monitor_assert_stable_link_up(TEST_IFACE)
def test_interface_ipv4_change(eth1_up):
    _modify_interface(
        ipv4_state={
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: False,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
    )

    ipv4_current_state = _get_ipv4_current_state(TEST_IFACE)

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
    _modify_interface(
        ipv4_state={
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.DHCP: True,
            InterfaceIPv4.ADDRESS: [],
        }
    )

    ipv4_current_state = _get_ipv4_current_state(TEST_IFACE)
    expected_ipv4_state = {
        InterfaceIPv4.ENABLED: True,
        InterfaceIPv4.DHCP: True,
        InterfaceIPv4.ADDRESS: [],
        InterfaceIPv4.AUTO_DNS: True,
        InterfaceIPv4.AUTO_GATEWAY: True,
        InterfaceIPv4.AUTO_ROUTES: True,
    }
    assert ipv4_current_state == expected_ipv4_state


@mainloop_run
def _modify_interface(ipv4_state):
    conn = nm.connection.ConnectionProfile()
    conn.import_by_id(TEST_IFACE)
    settings = _create_iface_settings(ipv4_state, conn)
    new_conn = nm.connection.ConnectionProfile()
    new_conn.create(settings)
    conn.update(new_conn)
    conn.commit(save_to_disk=False)

    nmdev = nm.device.get_device_by_name(TEST_IFACE)
    nm.device.reapply(nmdev, conn.profile)


@nmclient_context
def _get_ipv4_current_state(ifname):
    nmdev = nm.device.get_device_by_name(ifname)
    active_connection = nm.connection.get_device_active_connection(nmdev)
    return nm.ipv4.get_info(active_connection)


def _create_iface_settings(ipv4_state, con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(con_profile)

    ipv4_setting = nm.ipv4.create_setting(ipv4_state, con_profile.profile)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    return con_setting.setting, ipv4_setting, ipv6_setting
