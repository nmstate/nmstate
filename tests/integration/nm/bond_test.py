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

from contextlib import contextmanager

from libnmstate import nm

from .testlib import mainloop


BOND0 = 'bondtest0'
ETH1 = 'eth1'


def test_create_and_remove_bond(eth1_up):
    bond_options = {'mode': 'balance-rr', 'miimon': '140'}

    with _bond_interface(BOND0, bond_options):
        bond_current_state = _get_bond_current_state(BOND0)

        bond_desired_state = {
            'slaves': [],
            'options': bond_options
        }
        assert bond_desired_state == bond_current_state

    assert not _get_bond_current_state(BOND0)


@contextmanager
def _bond_interface(name, options):
    try:
        _create_bond(name, options)
        yield
    finally:
        _delete_bond(name)


def _get_bond_current_state(name):
    nm.nmclient.client(refresh=True)
    nmdev = nm.device.get_device_by_name(name)
    return nm.bond.get_bond_info(nmdev) if nmdev else {}


def _create_bond(name, options):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=name,
        iface_name=name,
        iface_type=nm.nmclient.NM.SETTING_BOND_SETTING_NAME,
    )
    bond_setting = nm.bond.create_setting(options)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    with mainloop():
        con_profile = nm.connection.ConnectionProfile()
        con_profile.create(
            (con_setting.setting, bond_setting, ipv4_setting, ipv6_setting))
        con_profile.add(save_to_disk=False)
        nm.device.activate(connection_id=name)


def _delete_bond(devname):
    nmdev = nm.device.get_device_by_name(devname)
    with mainloop():
        nm.device.deactivate(nmdev)
        nm.device.delete(nmdev)
