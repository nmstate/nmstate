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

from contextlib import contextmanager

from libnmstate import nm
from libnmstate import schema
from libnmstate.nm.common import NM
from libnmstate.schema import Bond
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from .testlib import mainloop


BOND0 = "bondtest0"


def test_create_and_remove_bond(eth1_up, nm_plugin):
    bond_options = {
        schema.Bond.MODE: schema.BondMode.ROUND_ROBIN,
        "miimon": "140",
    }

    with _bond_interface(nm_plugin.client, BOND0, bond_options):
        bond_current_state = _get_bond_current_state(
            nm_plugin, BOND0, "miimon"
        )

        bond_desired_state = {
            schema.Bond.SLAVES: [],
            schema.Bond.OPTIONS_SUBTREE: bond_options,
        }
        assert bond_current_state == bond_desired_state

    assert not _get_bond_current_state(nm_plugin, BOND0)


def test_bond_with_a_slave(eth1_up, nm_plugin):
    bond_options = {schema.Bond.MODE: schema.BondMode.ROUND_ROBIN}

    with _bond_interface(nm_plugin.client, BOND0, bond_options):
        nic_name = eth1_up[Interface.KEY][0][Interface.NAME]
        _attach_slave_to_bond(nm_plugin.client, BOND0, nic_name)

        bond_current_state = _get_bond_current_state(nm_plugin, BOND0)

        bond_desired_state = {
            schema.Bond.SLAVES: [nic_name],
            schema.Bond.OPTIONS_SUBTREE: bond_options,
        }
        assert bond_current_state == bond_desired_state

    assert not _get_bond_current_state(nm_plugin, BOND0)


@contextmanager
def _bond_interface(client, name, options):
    try:
        _create_bond(client, name, options)
        yield
    finally:
        _delete_bond(client, name)


def _get_bond_current_state(plugin, name, option=None):
    """
    When option defined, the returned state will only contains the
    specified bond option and the bond mode.
    When option not defined, the return state will only contains bond mode.
    This is needed for assert check.
    """
    plugin.refresh_content()
    nmdev = nm.device.get_device_by_name(plugin.client, name)
    nm_bond_info = nm.bond.get_bond_info(nmdev) if nmdev else {}
    if not nm_bond_info:
        return {}
    bond_options = nm_bond_info[schema.Bond.OPTIONS_SUBTREE]
    nm_bond_info[schema.Bond.OPTIONS_SUBTREE] = {
        schema.Bond.MODE: bond_options[schema.Bond.MODE]
    }
    if option:
        nm_bond_info[schema.Bond.OPTIONS_SUBTREE][option] = bond_options[
            option
        ]
    return _convert_slaves_devices_to_iface_names(nm_bond_info)


def _create_bond(client, name, options):
    con_setting = nm.connection.ConnectionSetting(client)
    con_setting.create(
        con_name=name,
        iface_name=name,
        iface_type=NM.SETTING_BOND_SETTING_NAME,
    )
    bond_setting = nm.bond.create_setting(options, wired_setting=None)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    con_profile = nm.connection.ConnectionProfile(client)
    con_profile.create(
        (con_setting.setting, bond_setting, ipv4_setting, ipv6_setting)
    )
    with mainloop():
        con_profile.add(save_to_disk=False)
        nm.device.activate(client, connection_id=name)


def _delete_bond(client, devname):
    with mainloop():
        nmdev = nm.device.get_device_by_name(client, devname)
        nm.device.deactivate(client, nmdev)
        nm.device.delete(client, nmdev)
        nm.device.delete_device(client, nmdev)


def _attach_slave_to_bond(client, bond, slave):
    slave_nmdev = nm.device.get_device_by_name(client, slave)
    curr_slave_con_profile = nm.connection.ConnectionProfile(client)
    curr_slave_con_profile.import_by_device(slave_nmdev)

    slave_con_profile = nm.connection.ConnectionProfile(client)
    slave_settings = [_create_connection_setting(bond, curr_slave_con_profile)]
    slave_con_profile.create(slave_settings)

    with mainloop():
        curr_slave_con_profile.update(slave_con_profile)
        nm.device.activate(client, connection_id=slave)


def _create_connection_setting(bond, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile)
    con_setting.set_master(bond, InterfaceType.BOND)

    return con_setting.setting


def _convert_slaves_devices_to_iface_names(info):
    if info:
        info[Bond.SLAVES] = [
            slave.props.interface for slave in info[Bond.SLAVES]
        ]
    return info
