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

import pytest

import libnmstate
from libnmstate import nm
from libnmstate import schema
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge as LB
from libnmstate.nm.common import NM

from ..testlib import iproutelib
from ..testlib import statelib
from ..testlib.bridgelib import linux_bridge
from ..testlib.dummy import nm_unmanaged_dummy
from .testlib import main_context


BRIDGE0 = "brtest0"
DUMMY1 = "dummy1"


@pytest.fixture
def bridge0_with_port0(port0_up, nm_plugin):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        yield _get_bridge_current_state()


def test_create_and_remove_minimum_config_bridge(nm_plugin):
    bridge_desired_state = {LB.CONFIG_SUBTREE: {LB.PORT_SUBTREE: []}}

    with _bridge_interface(nm_plugin.context, bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_current_state
        assert not bridge_current_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]

    assert not _get_bridge_current_state()


def test_create_and_remove_bridge(nm_plugin, port0_up):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        _remove_read_only_properties(bridge_current_state)
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


@iproutelib.ip_monitor_assert_stable_link_up(BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up, nm_plugin):
    port_name = port1_up[schema.Interface.KEY][0][schema.Interface.NAME]
    _add_ports_to_bridge_config(bridge0_with_port0, (port_name,))

    _modify_bridge(nm_plugin.context, bridge0_with_port0)

    current_state = _get_bridge_current_state()
    _remove_read_only_properties(current_state)
    _remove_read_only_properties(bridge0_with_port0)

    assert bridge0_with_port0 == current_state


def _add_ports_to_bridge_config(bridge_state, ports):
    ports_config = _create_bridge_ports_config(ports)
    bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] += ports_config


def _create_bridge_config(ports):
    ports_states = _create_bridge_ports_config(ports)
    bridge_config = {
        LB.CONFIG_SUBTREE: {
            LB.OPTIONS_SUBTREE: {
                LB.Options.GROUP_FORWARD_MASK: 0,
                LB.Options.MAC_AGEING_TIME: 300,
                LB.Options.MULTICAST_SNOOPING: True,
                LB.Options.MULTICAST_ROUTER: 1,
                LB.Options.GROUP_ADDR: "01:80:C2:00:00:00",
                LB.Options.HASH_MAX: 4096,
                LB.Options.MULTICAST_LAST_MEMBER_COUNT: 2,
                LB.Options.MULTICAST_LAST_MEMBER_INTERVAL: 100,
                LB.Options.MULTICAST_QUERIER: False,
                LB.Options.MULTICAST_QUERIER_INTERVAL: 25500,
                LB.Options.MULTICAST_QUERY_USE_IFADDR: False,
                LB.Options.MULTICAST_QUERY_INTERVAL: 12500,
                LB.Options.MULTICAST_QUERY_RESPONSE_INTERVAL: 1000,
                LB.Options.MULTICAST_STARTUP_QUERY_COUNT: 2,
                LB.Options.MULTICAST_STARTUP_QUERY_INTERVAL: 3000,
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
    return bridge_config


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
def _bridge_interface(ctx, state):
    con_profile = None
    port_profiles = []
    try:
        con_profile, port_profiles = _create_bridge(ctx, state)
        yield
    finally:
        _delete_iface(ctx, con_profile)
        for p in port_profiles:
            _delete_iface(ctx, p)


def _modify_bridge(ctx, bridge_desired_state):
    bridge_config = bridge_desired_state[LB.CONFIG_SUBTREE]
    with main_context(ctx):
        _modify_bridge_options(ctx, bridge_desired_state)
        _modify_ports(ctx, bridge_config[LB.PORT_SUBTREE])


def _modify_bridge_options(ctx, bridge_state):
    conn = nm.profile.NmProfile(ctx, True)
    conn._import_existing_profile(BRIDGE0)
    iface_bridge_settings = _create_iface_bridge_settings(bridge_state, conn)
    conn._simple_conn = nm.connection.create_new_simple_connection(
        iface_bridge_settings
    )
    conn._update()
    ctx.wait_all_finish()
    nm.device.modify(ctx, conn)
    ctx.wait_all_finish()


def _modify_ports(ctx, ports_state):
    for port_state in ports_state:
        _attach_port_to_bridge(ctx, port_state)


def _get_bridge_current_state():
    iface_states = statelib.show_only((BRIDGE0,))[Interface.KEY]
    if iface_states:
        return {LB.CONFIG_SUBTREE: iface_states[0][LB.CONFIG_SUBTREE]}
    else:
        return {}


def _create_bridge(ctx, bridge_desired_state):
    iface_bridge_settings = _create_iface_bridge_settings(bridge_desired_state)

    with main_context(ctx):
        con_profile = _create_bridge_iface(ctx, iface_bridge_settings)
        ports_state = bridge_desired_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
        port_profiles = []
        for port_state in ports_state:
            port_profile = _attach_port_to_bridge(ctx, port_state)
            port_profiles.append(port_profile)

    return con_profile, port_profiles


def _attach_port_to_bridge(ctx, port_state):
    curr_port_con_profile = nm.profile.NmProfile(ctx, True)
    curr_port_con_profile._import_existing_profile(port_state[Interface.NAME])
    iface_port_settings = _get_iface_port_settings(
        port_state, curr_port_con_profile
    )
    simple_conn = nm.connection.create_new_simple_connection(
        iface_port_settings
    )
    curr_port_con_profile._simple_conn = simple_conn

    curr_port_con_profile._update()
    ctx.wait_all_finish()
    nm.device.modify(ctx, curr_port_con_profile)
    return curr_port_con_profile


def _create_bridge_iface(ctx, iface_bridge_settings):
    br_con_profile = nm.profile.NmProfile(ctx, True)
    br_con_profile._simple_conn = nm.connection.create_new_simple_connection(
        iface_bridge_settings
    )
    br_con_profile._add()
    ctx.wait_all_finish()
    br_con_profile.activate()
    ctx.wait_all_finish()
    return br_con_profile


def _get_iface_port_settings(port_state, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile.profile)
    con_setting.set_master(BRIDGE0, "bridge")

    bridge_port_setting = nm.bridge.create_port_setting(
        port_state, port_con_profile.profile
    )
    return con_setting.setting, bridge_port_setting


def _delete_iface(ctx, con_profile):
    with main_context(ctx):
        if con_profile:
            nm.device.deactivate(ctx, con_profile.nmdev)
            ctx.wait_all_finish()
            con_profile.delete()


def _create_iface_bridge_settings(bridge_state, base_con_profile=None):
    con_profile = None
    con_setting = nm.connection.ConnectionSetting()
    if base_con_profile:
        con_setting.import_by_profile(base_con_profile.profile)
        con_profile = base_con_profile.profile
    else:
        con_setting.create(
            con_name=BRIDGE0,
            iface_name=BRIDGE0,
            iface_type=NM.SETTING_BRIDGE_SETTING_NAME,
        )
    bridge_setting = nm.bridge.create_setting(
        bridge_state, con_profile, bridge_state
    )
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    return con_setting.setting, bridge_setting, ipv4_setting, ipv6_setting


def _remove_read_only_properties(bridge_state):
    bridge_options = bridge_state.get(LB.CONFIG_SUBTREE, {}).get(
        LB.OPTIONS_SUBTREE, {}
    )
    if bridge_options:
        for key in (LB.Options.HELLO_TIMER, LB.Options.GC_TIMER):
            bridge_options.pop(key, None)


@pytest.fixture
def nm_unmanaged_dummy1():
    with nm_unmanaged_dummy(DUMMY1):
        yield


@pytest.mark.tier1
def test_bridge_as_port_unmanaged_interface(nm_unmanaged_dummy1):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}}
        },
    ) as desired_state:
        bridge_iface_state = desired_state[Interface.KEY][0]
        bridge_iface_state[LB.CONFIG_SUBTREE] = {
            LB.PORT_SUBTREE: [{LB.Port.NAME: DUMMY1}],
        }
        # To reproduce bug https://bugzilla.redhat.com/1816517
        # explitly define dummy1 as IPv4/IPv6 disabled is required.
        desired_state[Interface.KEY].append(
            {
                Interface.NAME: DUMMY1,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        )
        libnmstate.apply(desired_state)
