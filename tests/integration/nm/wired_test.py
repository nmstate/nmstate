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
from libnmstate import schema
from libnmstate.nm.nmclient import nmclient_context

from .testlib import mainloop_run


ETH1 = "eth1"

MAC0 = "02:FF:FF:FF:FF:00"
MTU0 = 1200


def test_interface_mtu_change_with_modify(eth1_up):
    _test_interface_mtu_change(nm.device.modify)


def _test_interface_mtu_change(apply_operation):
    wired_base_state = _get_wired_current_state(ETH1)
    _modify_interface(
        wired_state={schema.Interface.MTU: MTU0},
        apply_operation=apply_operation,
    )

    wired_current_state = _get_wired_current_state(ETH1)

    assert wired_current_state == {
        schema.Interface.MAC: wired_base_state[schema.Interface.MAC],
        schema.Interface.MTU: MTU0,
    }


def test_interface_mac_change_with_modify(eth1_up):
    _test_interface_mac_change(nm.device.modify)


def _test_interface_mac_change(apply_operation):
    wired_base_state = _get_wired_current_state(ETH1)
    _modify_interface(
        wired_state={schema.Interface.MAC: MAC0},
        apply_operation=apply_operation,
    )

    wired_current_state = _get_wired_current_state(ETH1)

    assert wired_current_state == {
        schema.Interface.MAC: MAC0,
        schema.Interface.MTU: wired_base_state[schema.Interface.MTU],
    }


@mainloop_run
def _modify_interface(wired_state, apply_operation):
    conn = nm.connection.ConnectionProfile()
    conn.import_by_id(ETH1)
    settings = _create_iface_settings(wired_state, conn)
    new_conn = nm.connection.ConnectionProfile()
    new_conn.create(settings)
    conn.update(new_conn)
    conn.commit(save_to_disk=False)

    nmdev = nm.device.get_device_by_name(ETH1)
    apply_operation(nmdev, conn.profile)


@nmclient_context
def _get_wired_current_state(ifname):
    nmdev = nm.device.get_device_by_name(ifname)
    return nm.wired.get_info(nmdev) if nmdev else {}


def _create_iface_settings(wired_state, con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(con_profile)

    wired_setting = nm.wired.create_setting(wired_state, con_profile.profile)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    return con_setting.setting, wired_setting, ipv4_setting, ipv6_setting
