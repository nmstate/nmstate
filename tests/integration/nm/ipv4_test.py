#
# Copyright 2019 Red Hat, Inc.
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

from libnmstate import nm

from ..testlib import iproutelib
from .testlib import mainloop


TEST_IFACE = 'eth1'

IPV4_ADDRESS1 = '192.0.2.251'


@iproutelib.ip_monitor_assert_stable_link_up(TEST_IFACE)
def test_interface_ipv4_change(eth1_up):
    with mainloop():
        _modify_interface(
            ipv4_state={
                'enabled': True,
                'dhcp': False,
                'address': [{'ip': IPV4_ADDRESS1, 'prefix-length': 24}],
            }
        )

    nm.nmclient.client(refresh=True)
    ipv4_current_state = _get_ipv4_current_state(TEST_IFACE)

    ip4_expected_state = {
        'enabled': True,
        'dhcp': False,
        'address': [{'ip': IPV4_ADDRESS1, 'prefix-length': 24}],
    }
    assert ip4_expected_state == ipv4_current_state


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


def _get_ipv4_current_state(ifname):
    nmdev = nm.device.get_device_by_name(ifname)
    active_connection = nm.connection.get_device_active_connection(nmdev)
    return nm.ipv4.get_info(active_connection)


def _create_iface_settings(ipv4_state, con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(con_profile)

    # Wired is required due to https://bugzilla.redhat.com/1703960
    wired_setting = con_profile.profile.get_setting_wired()

    ipv4_setting = nm.ipv4.create_setting(ipv4_state, con_profile.profile)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    return con_setting.setting, wired_setting, ipv4_setting, ipv6_setting
