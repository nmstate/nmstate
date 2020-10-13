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
from libnmstate.nm.common import NM
from libnmstate.ifaces.bond import BondIface
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from .testlib import main_context
from ..testlib import statelib
from ..testlib.retry import retry_till_true_or_timeout


BOND0 = "bondtest0"
VERIFY_RETRY_TMO = 5


def _gen_bond_iface(bond_options, mode=BondMode.ROUND_ROBIN):
    return BondIface(
        {
            Interface.NAME: "foo",
            Interface.TYPE: InterfaceType.BOND,
            Bond.CONFIG_SUBTREE: {
                Bond.MODE: mode,
                Bond.OPTIONS_SUBTREE: bond_options,
            },
        }
    )


def test_create_and_remove_bond(eth1_up, nm_plugin):
    bond_options = {"miimon": 140}

    with _bond_interface(
        nm_plugin.context, BOND0, BondMode.ROUND_ROBIN, bond_options
    ):
        bond_current_state = _get_bond_current_state(BOND0, "miimon")

        bond_desired_state = {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.PORT: [],
            Bond.OPTIONS_SUBTREE: bond_options,
        }
        assert bond_current_state == bond_desired_state

    assert not _get_bond_current_state(BOND0)


def test_bond_with_a_port(eth1_up, nm_plugin):
    bond_options = {"miimon": 140}
    with _bond_interface(
        nm_plugin.context, BOND0, BondMode.ROUND_ROBIN, bond_options
    ):
        nic_name = eth1_up[Interface.KEY][0][Interface.NAME]
        _attach_port_to_bond(nm_plugin.context, BOND0, nic_name)
        bond_desired_state = {
            Bond.MODE: BondMode.ROUND_ROBIN,
            Bond.PORT: [nic_name],
            Bond.OPTIONS_SUBTREE: bond_options,
        }

        assert retry_till_true_or_timeout(
            VERIFY_RETRY_TMO, _verify_bond_state, "miimon", bond_desired_state
        )

    assert not _get_bond_current_state(BOND0)


@contextmanager
def _bond_interface(ctx, name, mode, options):
    con_profile = None
    try:
        con_profile = _create_bond(ctx, name, mode, options)
        yield
    finally:
        _delete_bond(ctx, con_profile)


def _get_bond_current_state(name, option=None):
    """
    When option defined, the returned state will only contains the
    specified bond option and the bond mode.
    When option not defined, the return state will only contains bond mode.
    This is needed for assert check.
    """
    state = statelib.show_only((name,))
    if len(state[Interface.KEY]) < 1:
        return None
    bond_info = state[Interface.KEY][0][Bond.CONFIG_SUBTREE]
    if option:
        return {
            Bond.MODE: bond_info[Bond.MODE],
            Bond.PORT: bond_info[Bond.PORT],
            Bond.OPTIONS_SUBTREE: {
                option: bond_info[Bond.OPTIONS_SUBTREE][option]
            },
        }
    else:
        return bond_info


def _create_bond(ctx, name, mode, options):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=name,
        iface_name=name,
        iface_type=NM.SETTING_BOND_SETTING_NAME,
    )
    iface = _gen_bond_iface(options, mode)
    bond_setting = nm.bond.create_setting(
        iface, wired_setting=None, base_con_profile=None
    )
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    con_profile = nm.profile.NmProfile(ctx, True)
    simple_conn = nm.connection.create_new_simple_connection(
        (con_setting.setting, bond_setting, ipv4_setting, ipv6_setting)
    )
    con_profile._simple_conn = simple_conn
    with main_context(ctx):
        con_profile._add()
        ctx.wait_all_finish()
        con_profile.activate()
        ctx.wait_all_finish()
        return con_profile


def _delete_bond(ctx, profile):
    with main_context(ctx):
        if profile:
            nm.device.deactivate(ctx, profile.nmdev)
            ctx.wait_all_finish()
            profile.delete()
            ctx.wait_all_finish()
            nm.device.delete_device(ctx, profile.nmdev)


def _attach_port_to_bond(ctx, bond, port):
    curr_port_con_profile = nm.profile.NmProfile(ctx, True)
    curr_port_con_profile._import_existing_profile(port)

    port_settings = [_create_connection_setting(bond, curr_port_con_profile)]
    simple_conn = nm.connection.create_new_simple_connection(port_settings)
    curr_port_con_profile._simple_conn = simple_conn

    with main_context(ctx):
        curr_port_con_profile._update()
        ctx.wait_all_finish()
        curr_port_con_profile.activate()
        ctx.wait_all_finish()


def _create_connection_setting(bond, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile.profile)
    con_setting.set_controller(bond, InterfaceType.BOND)

    return con_setting.setting


def _verify_bond_state(option, expected_state):
    return _get_bond_current_state(BOND0, option) == expected_state
