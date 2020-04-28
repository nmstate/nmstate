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
from operator import itemgetter

import pytest

from libnmstate import nm
from libnmstate import schema
from libnmstate.schema import LinuxBridge as LB
from libnmstate.nm.common import NM

from ..testlib import iproutelib
from .testlib import mainloop


BRIDGE0 = "brtest0"


@pytest.fixture
def bridge0_with_port0(port0_up, nm_plugin):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(nm_plugin.client, bridge_desired_state):
        yield _get_bridge_current_state(nm_plugin)


def test_create_and_remove_minimum_config_bridge(nm_plugin):
    bridge_desired_state = {LB.CONFIG_SUBTREE: {LB.PORT_SUBTREE: []}}

    with _bridge_interface(nm_plugin.client, bridge_desired_state):

        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_current_state
        assert not bridge_current_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]

    assert not _get_bridge_current_state(nm_plugin)


def test_create_and_remove_bridge(nm_plugin, port0_up):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(nm_plugin.client, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state(nm_plugin)


@iproutelib.ip_monitor_assert_stable_link_up(BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up, nm_plugin):
    port_name = port1_up[schema.Interface.KEY][0][schema.Interface.NAME]
    _add_ports_to_bridge_config(bridge0_with_port0, (port_name,))

    _modify_bridge(nm_plugin.client, bridge0_with_port0)

    assert bridge0_with_port0 == _get_bridge_current_state(nm_plugin)


def _add_ports_to_bridge_config(bridge_state, ports):
    ports_config = _create_bridge_ports_config(ports)
    bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] += ports_config


def _create_bridge_config(ports):
    ports_states = _create_bridge_ports_config(ports)
    return {
        LB.CONFIG_SUBTREE: {
            LB.OPTIONS_SUBTREE: {
                LB.Options.GROUP_FORWARD_MASK: 0,
                LB.Options.MAC_AGEING_TIME: 300,
                LB.Options.MULTICAST_SNOOPING: True,
                LB.STP_SUBTREE: {
                    # Disable STP to avoid topology changes and the consequence
                    # link change.
                    LB.STP.ENABLED: False,
                    LB.STP.FORWARD_DELAY: 15,
                    LB.STP.HELLO_TIME: 2,
                    LB.STP.MAX_AGE: 20,
                    LB.STP.PRIORITY: 32768,
                },
            },
            LB.PORT_SUBTREE: ports_states,
        }
    }


def _create_bridge_ports_config(ports):
    return [
        {
            LB.Port.NAME: port,
            LB.Port.STP_PRIORITY: 32,
            LB.Port.STP_HAIRPIN_MODE: False,
            LB.Port.STP_PATH_COST: 100,
        }
        for port in ports
    ]


@contextmanager
def _bridge_interface(client, state):
    try:
        _create_bridge(client, state)
        yield
    finally:
        _delete_iface(client, BRIDGE0)
        for p in state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]:
            _delete_iface(client, p[LB.Port.NAME])


def _modify_bridge(client, bridge_desired_state):
    bridge_config = bridge_desired_state[LB.CONFIG_SUBTREE]
    with mainloop():
        _modify_bridge_options(client, bridge_desired_state)
        _modify_ports(client, bridge_config[LB.PORT_SUBTREE])


def _modify_bridge_options(client, bridge_state):
    br_options = bridge_state.get(LB.CONFIG_SUBTREE, {}).get(
        LB.OPTIONS_SUBTREE
    )
    nmdev = nm.device.get_device_by_name(client, BRIDGE0)
    conn = nm.connection.ConnectionProfile(client)
    conn.import_by_id(BRIDGE0)
    iface_bridge_settings = _create_iface_bridge_settings(br_options, conn)
    new_conn = nm.connection.ConnectionProfile(client)
    new_conn.create(iface_bridge_settings)
    conn.update(new_conn)
    nm.device.modify(client, nmdev, new_conn.profile)


def _modify_ports(client, ports_state):
    for port_state in ports_state:
        _attach_port_to_bridge(client, port_state)


def _get_bridge_current_state(nm_plugin):
    nm_plugin.refresh_content()
    nmdev = nm.device.get_device_by_name(nm_plugin.client, BRIDGE0)
    info = nm.bridge.get_info(nm_plugin.client, nmdev) if nmdev else {}
    info.get(LB.CONFIG_SUBTREE, {}).get(LB.PORT_SUBTREE, []).sort(
        key=itemgetter(LB.Port.NAME)
    )
    return info


def _create_bridge(client, bridge_desired_state):
    iface_bridge_settings = _create_iface_bridge_settings(bridge_desired_state)

    with mainloop():
        _create_bridge_iface(client, iface_bridge_settings)
        ports_state = bridge_desired_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
        for port_state in ports_state:
            _attach_port_to_bridge(client, port_state)


def _attach_port_to_bridge(client, port_state):
    port_nmdev = nm.device.get_device_by_name(client, port_state["name"])
    curr_port_con_profile = nm.connection.ConnectionProfile(client)
    curr_port_con_profile.import_by_device(port_nmdev)
    iface_port_settings = _get_iface_port_settings(
        port_state, curr_port_con_profile
    )
    port_con_profile = nm.connection.ConnectionProfile(client)
    port_con_profile.create(iface_port_settings)

    curr_port_con_profile.update(port_con_profile)
    nm.device.modify(client, port_nmdev, port_con_profile.profile)


def _create_bridge_iface(client, iface_bridge_settings):
    br_con_profile = nm.connection.ConnectionProfile(client)
    br_con_profile.create(iface_bridge_settings)
    br_con_profile.add(save_to_disk=False)
    nm.device.activate(client, connection_id=BRIDGE0)


def _get_iface_port_settings(port_state, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile)
    con_setting.set_master(BRIDGE0, "bridge")

    bridge_port_setting = nm.bridge.create_port_setting(
        port_state, port_con_profile.profile
    )
    return con_setting.setting, bridge_port_setting


def _delete_iface(client, devname):
    nmdev = nm.device.get_device_by_name(client, devname)
    with mainloop():
        nm.device.deactivate(client, nmdev)
        nm.device.delete(client, nmdev)


def _create_iface_bridge_settings(bridge_state, base_con_profile=None):
    con_profile = None
    con_setting = nm.connection.ConnectionSetting()
    if base_con_profile:
        con_setting.import_by_profile(base_con_profile)
        con_profile = base_con_profile.profile
    else:
        con_setting.create(
            con_name=BRIDGE0,
            iface_name=BRIDGE0,
            iface_type=NM.SETTING_BRIDGE_SETTING_NAME,
        )
    bridge_setting = nm.bridge.create_setting(bridge_state, con_profile)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    return con_setting.setting, bridge_setting, ipv4_setting, ipv6_setting
