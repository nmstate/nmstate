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

from contextlib import contextmanager

from libnmstate import nm

from .testlib import mainloop


ETH1 = 'eth1'


def test_create_and_remove_vlan(eth1_up):
    vlan_desired_state = {'vlan': {'id': 101, 'base-iface': ETH1}}

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


def _get_vlan_current_state(vlan_desired_state):
    nm.nmclient.client(refresh=True)
    ifname = _get_vlan_ifname(vlan_desired_state)
    nmdev = nm.device.get_device_by_name(ifname)
    return nm.vlan.get_info(nmdev) if nmdev else {}


def _create_vlan(vlan_desired_state):
    ifname = _get_vlan_ifname(vlan_desired_state)
    con_setting = nm.connection.create_setting(
        con_name=ifname,
        iface_name=ifname,
        iface_type=nm.nmclient.NM.SETTING_VLAN_SETTING_NAME,
    )
    vlan_setting = nm.vlan.create_setting(vlan_desired_state,
                                          base_con_profile=None)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    with mainloop():
        con_profile = nm.connection.create_profile(
            (con_setting, vlan_setting, ipv4_setting, ipv6_setting))
        nm.connection.add_profile(con_profile, save_to_disk=False)
        nm.device.activate(connection_id=ifname)


def _delete_vlan(devname):
    nmdev = nm.device.get_device_by_name(devname)
    with mainloop():
        nm.device.deactivate(nmdev)
        nm.device.delete(nmdev)


def _get_vlan_ifname(state):
    return state['vlan']['base-iface'] + '.' + str(state['vlan']['id'])
