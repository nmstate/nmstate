#
# Copyright (c) 2018-2021 Red Hat, Inc.
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
import time

import pytest

import libnmstate
from libnmstate import nm
from libnmstate import schema
from libnmstate.schema import Bridge
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import LinuxBridge as LB
from libnmstate.nm.common import NM

from ..testlib import cmdlib
from ..testlib import iproutelib
from ..testlib.bridgelib import linux_bridge
from .testlib import main_context


BRIDGE0 = "brtest0"
DUMMY1 = "dummy1"
ETH1 = "eth1"


@pytest.fixture
def bridge0_with_port0(port0_up, nm_plugin):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        yield _get_bridge_current_state(nm_plugin)


def test_create_and_remove_minimum_config_bridge(nm_plugin):
    bridge_desired_state = {LB.CONFIG_SUBTREE: {LB.PORT_SUBTREE: []}}

    with _bridge_interface(nm_plugin.context, bridge_desired_state):

        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_current_state
        assert not bridge_current_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]

    assert not _get_bridge_current_state(nm_plugin)


def test_create_and_remove_bridge(nm_plugin, port0_up):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state(nm_plugin)
        _remove_read_only_properties(bridge_current_state)
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state(nm_plugin)


@iproutelib.ip_monitor_assert_stable_link_up(BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up, nm_plugin):
    port_name = port1_up[schema.Interface.KEY][0][schema.Interface.NAME]
    _add_ports_to_bridge_config(bridge0_with_port0, (port_name,))

    _modify_bridge(nm_plugin.context, bridge0_with_port0)

    current_state = _get_bridge_current_state(nm_plugin)
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
    try:
        _create_bridge(ctx, state)
        yield
    finally:
        _delete_iface(ctx, BRIDGE0)
        for p in state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]:
            _delete_iface(ctx, p[LB.Port.NAME])


def _modify_bridge(ctx, bridge_desired_state):
    bridge_config = bridge_desired_state[LB.CONFIG_SUBTREE]
    with main_context(ctx):
        _modify_bridge_options(ctx, bridge_desired_state)
        _modify_ports(ctx, bridge_config[LB.PORT_SUBTREE])


def _modify_bridge_options(ctx, bridge_state):
    nmdev = ctx.get_nm_dev(BRIDGE0)
    conn = nm.connection.ConnectionProfile(ctx)
    conn.import_by_id(BRIDGE0)
    iface_bridge_settings = _create_iface_bridge_settings(bridge_state, conn)
    new_conn = nm.connection.ConnectionProfile(ctx)
    new_conn.create(iface_bridge_settings)
    conn.update(new_conn)
    ctx.wait_all_finish()
    nm.device.modify(ctx, nmdev, new_conn.profile)


def _modify_ports(ctx, ports_state):
    for port_state in ports_state:
        _attach_port_to_bridge(ctx, port_state)


def _get_bridge_current_state(nm_plugin):
    nm_plugin.refresh_content()
    nmdev = nm_plugin.context.get_nm_dev(BRIDGE0)
    info = nm.bridge.get_info(nm_plugin.context, nmdev) if nmdev else {}
    info.get(LB.CONFIG_SUBTREE, {}).get(LB.PORT_SUBTREE, []).sort(
        key=itemgetter(LB.Port.NAME)
    )
    return info


def _create_bridge(ctx, bridge_desired_state):
    iface_bridge_settings = _create_iface_bridge_settings(bridge_desired_state)

    with main_context(ctx):
        _create_bridge_iface(ctx, iface_bridge_settings)
        ports_state = bridge_desired_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
        for port_state in ports_state:
            _attach_port_to_bridge(ctx, port_state)


def _attach_port_to_bridge(ctx, port_state):
    port_nmdev = ctx.get_nm_dev(port_state["name"])
    curr_port_con_profile = nm.connection.ConnectionProfile(ctx)
    curr_port_con_profile.import_by_device(port_nmdev)
    iface_port_settings = _get_iface_port_settings(
        port_state, curr_port_con_profile
    )
    port_con_profile = nm.connection.ConnectionProfile(ctx)
    port_con_profile.create(iface_port_settings)

    curr_port_con_profile.update(port_con_profile)
    ctx.wait_all_finish()
    nm.device.modify(ctx, port_nmdev, port_con_profile.profile)


def _create_bridge_iface(ctx, iface_bridge_settings):
    br_con_profile = nm.connection.ConnectionProfile(ctx)
    br_con_profile.create(iface_bridge_settings)
    br_con_profile.add()
    ctx.wait_all_finish()
    nm.device.activate(ctx, connection_id=BRIDGE0)


def _get_iface_port_settings(port_state, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile)
    con_setting.set_master(BRIDGE0, "bridge")

    bridge_port_setting = nm.bridge.create_port_setting(
        port_state, port_con_profile.profile
    )
    return con_setting.setting, bridge_port_setting


def _delete_iface(ctx, devname):
    nmdev = ctx.get_nm_dev(devname)
    with main_context(ctx):
        nm.device.deactivate(ctx, nmdev)
        nm.device.delete(ctx, nmdev)


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
    cmdlib.exec_cmd(
        f"ip link add name {DUMMY1} type dummy".split(" "), check=True
    )
    cmdlib.exec_cmd(f"ip link set {DUMMY1} up".split(" "), check=True)
    cmdlib.exec_cmd(
        f"nmcli dev set {DUMMY1} managed yes".split(" "), check=True
    )
    time.sleep(1)  # Wait device became managed
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        },
        verify_change=False,
    )


@pytest.mark.tier1
def test_bridge_enslave_unmanaged_interface(nm_unmanaged_dummy1):
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


@pytest.fixture
def nm_down_unmanaged_dummy1():
    cmdlib.exec_cmd(
        f"ip link add name {DUMMY1} type dummy".split(" "), check=True
    )
    yield
    cmdlib.exec_cmd(
        f"nmcli dev set {DUMMY1} managed yes".split(" "), check=True
    )
    time.sleep(1)  # Wait device became managed
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        },
        verify_change=False,
    )


@pytest.mark.tier1
def test_reapply_bridge_state_does_not_managed_ports(nm_down_unmanaged_dummy1):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}}
        },
    ) as desired_state:
        cmdlib.exec_cmd(
            f"ip link set {DUMMY1} master {BRIDGE0}".split(), check=True
        )
        libnmstate.apply(desired_state)
        _, out, _ = cmdlib.exec_cmd(
            f"nmcli -f GENERAL.STATE d show {DUMMY1}".split(), check=True
        )

        assert "unmanaged" in out


@pytest.mark.tier1
def test_remove_bridge_manage_not_managed_port(nm_down_unmanaged_dummy1):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}}
        },
    ):
        cmdlib.exec_cmd(
            f"ip link set {DUMMY1} master {BRIDGE0}".split(), check=True
        )

    _, out, _ = cmdlib.exec_cmd(
        f"nmcli -f GENERAL.STATE d show {DUMMY1}".split(), check=True
    )

    assert "unmanaged" in out


@pytest.mark.tier1
def test_attach_port_does_not_manage_unmanage_ports(nm_down_unmanaged_dummy1):
    with linux_bridge(
        BRIDGE0,
        bridge_subtree_state={
            LB.OPTIONS_SUBTREE: {LB.STP_SUBTREE: {LB.STP.ENABLED: False}}
        },
    ) as desired_state:
        cmdlib.exec_cmd(
            f"ip link set {DUMMY1} master {BRIDGE0}".split(), check=True
        )
        bridge_iface_state = desired_state[Interface.KEY][0]
        bridge_iface_state[LB.CONFIG_SUBTREE] = {
            LB.PORT_SUBTREE: [{Bridge.Port.NAME: ETH1}]
        }
        libnmstate.apply(desired_state)
        _, out, _ = cmdlib.exec_cmd(
            f"nmcli -f GENERAL.STATE d show {DUMMY1}".split(), check=True
        )

        assert "unmanaged" in out
