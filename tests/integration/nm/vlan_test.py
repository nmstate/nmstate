#
# Copyright (c) 2018-2020 Red Hat, Inc.
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

from contextlib import contextmanager

from libnmstate import nm
from libnmstate.nm.nmclient import nmclient_context
from libnmstate.schema import VLAN

from .testlib import mainloop


ETH1 = "eth1"


def test_create_and_remove_vlan(eth1_up):
    vlan_desired_state = {
        VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: ETH1}
    }

    with _vlan_interface(vlan_desired_state):

        vlan_current_state = _get_vlan_current_state(vlan_desired_state)
        assert vlan_desired_state == vlan_current_state

    assert not _get_vlan_current_state(vlan_desired_state)


@contextmanager
def _vlan_interface(state):
    try:
        _create_vlan(state)
        yield
    finally:
        _delete_vlan(_get_vlan_ifname(state))


@nmclient_context
def _get_vlan_current_state(vlan_desired_state):
    ifname = _get_vlan_ifname(vlan_desired_state)
    nmdev = nm.device.get_device_by_name(ifname)
    return nm.vlan.get_info(nmdev) if nmdev else {}


@nmclient_context
def _create_vlan(vlan_desired_state):
    ifname = _get_vlan_ifname(vlan_desired_state)
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=ifname,
        iface_name=ifname,
        iface_type=nm.nmclient.NM.SETTING_VLAN_SETTING_NAME,
    )
    vlan_setting = nm.vlan.create_setting(
        vlan_desired_state, base_con_profile=None
    )
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    with mainloop():
        con_profile = nm.connection.ConnectionProfile()
        con_profile.create(
            (con_setting.setting, vlan_setting, ipv4_setting, ipv6_setting)
        )
        con_profile.add(save_to_disk=False)
        nm.device.activate(connection_id=ifname)


@nmclient_context
def _delete_vlan(devname):
    nmdev = nm.device.get_device_by_name(devname)
    with mainloop():
        nm.device.deactivate(nmdev)
        nm.device.delete(nmdev)


def _get_vlan_ifname(state):
    return (
        state[VLAN.CONFIG_SUBTREE][VLAN.BASE_IFACE]
        + "."
        + str(state[VLAN.CONFIG_SUBTREE][VLAN.ID])
    )
