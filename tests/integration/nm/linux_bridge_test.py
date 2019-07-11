#
# Copyright (c) 2018-2019 Red Hat, Inc.
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
from collections import namedtuple

import pytest

from libnmstate import nm
from libnmstate import schema
from libnmstate.schema import LinuxBridge as LB

from ..testlib import iproutelib
from .testlib import mainloop_run


PortConfig = namedtuple('PortConfig', ['name', 'vlan_config'])

BRIDGE0 = 'brtest0'


@pytest.fixture
def bridge0_with_port0(port0_up):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config(
        (PortConfig(port_name, vlan_config=[]),)
    )
    with _bridge_interface(bridge_desired_state):
        yield _get_bridge_current_state()


def test_create_and_remove_minimum_config_bridge():
    bridge_desired_state = {LB.CONFIG_SUBTREE: {LB.PORT_SUBTREE: []}}

    with _bridge_interface(bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_current_state
        assert not bridge_current_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]

    assert not _get_bridge_current_state()


def test_create_and_remove_bridge(port0_up):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config(
        (PortConfig(port_name, vlan_config=[]),)
    )
    with _bridge_interface(bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


@iproutelib.ip_monitor_assert_stable_link_up(BRIDGE0)
def test_add_port_to_existing_bridge(bridge0_with_port0, port1_up):
    port_name = port1_up[schema.Interface.KEY][0][schema.Interface.NAME]
    _add_ports_to_bridge_config_by_name(bridge0_with_port0, (port_name,))

    _modify_bridge(bridge0_with_port0)

    assert bridge0_with_port0 == _get_bridge_current_state()


def test_vlan_filtering_single_vlan(port0_up):
    bridge_desired_state = _create_bridge_config(ports=[])
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    port = PortConfig(port_name, vlan_config=[{'vlan-range-min': 101}])
    _add_ports_to_bridge_config(bridge_desired_state, (port,))

    with _bridge_interface(bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


def test_vlan_filtering_with_range(port0_up):
    bridge_desired_state = _create_bridge_config(ports=[])
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    port_config = PortConfig(
        port_name,
        vlan_config=[
            {'vlan-range-min': 101, 'vlan-range-max': 201},
            {'vlan-range-min': 500, 'vlan-range-max': 600},
        ],
    )
    _add_ports_to_bridge_config(bridge_desired_state, (port_config,))

    with _bridge_interface(bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


def _add_ports_to_bridge_config_by_name(bridge_state, port_names):
    port_configs = [
        PortConfig(port_name, vlan_config=[]) for port_name in port_names
    ]
    ports_config = _create_bridge_ports_config(port_configs)
    bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE] += ports_config


def _add_ports_to_bridge_config(bridge_state, port_configs):
    bridge_ports = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
    bridge_ports += _create_bridge_ports_config(port_configs)


def _create_bridge_config(ports):
    ports_states = _create_bridge_ports_config(ports)
    return {
        LB.CONFIG_SUBTREE: {
            LB.OPTIONS_SUBTREE: {
                LB.GROUP_FORWARD_MASK: 0,
                LB.MAC_AGEING_TIME: 300,
                LB.MULTICAST_SNOOPING: True,
                LB.STP_SUBTREE: {
                    # Disable STP to avoid topology changes and the consequence
                    # link change.
                    LB.STP_ENABLED: False,
                    LB.STP_FORWARD_DELAY: 15,
                    LB.STP_HELLO_TIME: 2,
                    LB.STP_MAX_AGE: 20,
                    LB.STP_PRIORITY: 32768,
                },
                LB.VLAN_FILTERING: True,
                LB.VLANS: [],
            },
            LB.PORT_SUBTREE: ports_states,
        }
    }


def _create_bridge_ports_config(ports):
    return [
        _create_bridge_port_config(port.name, port.vlan_config)
        for port in ports
    ]


def _create_bridge_port_config(port_name, vlan_config):
    return {
        LB.PORT_NAME: port_name,
        LB.PORT_STP_PRIORITY: 32,
        LB.PORT_STP_HAIRPIN_MODE: False,
        LB.PORT_STP_PATH_COST: 100,
        LB.PORT_VLANS: vlan_config,
    }


@contextmanager
def _bridge_interface(state):
    try:
        _create_bridge(state)
        yield
    finally:
        _delete_iface(BRIDGE0)
        for p in state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]:
            _delete_iface(p[LB.PORT_NAME])


@mainloop_run
def _modify_bridge(bridge_desired_state):
    bridge_config = bridge_desired_state[LB.CONFIG_SUBTREE]
    _modify_bridge_options(bridge_config)
    _modify_ports(bridge_config[LB.PORT_SUBTREE])


def _modify_bridge_options(bridge_config):
    br_options = bridge_config.get(LB.OPTIONS_SUBTREE)
    nmdev = nm.device.get_device_by_name(BRIDGE0)
    conn = nm.connection.ConnectionProfile()
    conn.import_by_id(BRIDGE0)
    iface_bridge_settings = _create_iface_bridge_settings(br_options, conn)
    new_conn = nm.connection.ConnectionProfile()
    new_conn.create(iface_bridge_settings)
    conn.update(new_conn)
    conn.commit(save_to_disk=False, nmdev=nmdev)
    nm.device.modify(nmdev, conn.profile)


def _modify_ports(ports_state):
    for port_state in ports_state:
        _attach_port_to_bridge(port_state)


def _get_bridge_current_state():
    nm.nmclient.client(refresh=True)
    nmdev = nm.device.get_device_by_name(BRIDGE0)
    return nm.bridge.get_info(nmdev) if nmdev else {}


@mainloop_run
def _create_bridge(bridge_desired_state):
    bridge_config = bridge_desired_state.get(LB.CONFIG_SUBTREE, {})
    br_options = bridge_config.get(LB.OPTIONS_SUBTREE)
    iface_bridge_settings = _create_iface_bridge_settings(br_options)

    _create_bridge_iface(iface_bridge_settings)
    ports_state = bridge_desired_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
    for port_state in ports_state:
        _attach_port_to_bridge(port_state)


def _attach_port_to_bridge(port_state):
    port_nmdev = nm.device.get_device_by_name(port_state['name'])
    curr_port_con_profile = nm.connection.ConnectionProfile()
    curr_port_con_profile.import_by_device(port_nmdev)
    iface_port_settings = _get_iface_port_settings(
        port_state, curr_port_con_profile
    )
    port_con_profile = nm.connection.ConnectionProfile()
    port_con_profile.create(iface_port_settings)

    curr_port_con_profile.update(port_con_profile)
    curr_port_con_profile.commit(nmdev=port_nmdev)
    nm.device.modify(port_nmdev, curr_port_con_profile.profile)


def _create_bridge_iface(iface_bridge_settings):
    br_con_profile = nm.connection.ConnectionProfile()
    br_con_profile.create(iface_bridge_settings)
    br_con_profile.add(save_to_disk=False)
    nm.device.activate(connection_id=BRIDGE0)


def _get_iface_port_settings(port_state, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile)
    con_setting.set_master(BRIDGE0, 'bridge')

    bridge_port_setting = nm.bridge.create_port_setting(
        port_state, port_con_profile.profile
    )
    return con_setting.setting, bridge_port_setting


@mainloop_run
def _delete_iface(devname):
    nmdev = nm.device.get_device_by_name(devname)
    nm.device.deactivate(nmdev)
    nm.device.delete(nmdev)


def _create_iface_bridge_settings(bridge_options, base_con_profile=None):
    con_profile = None
    con_setting = nm.connection.ConnectionSetting()
    if base_con_profile:
        con_setting.import_by_profile(base_con_profile)
        con_profile = base_con_profile.profile
    else:
        con_setting.create(
            con_name=BRIDGE0,
            iface_name=BRIDGE0,
            iface_type=nm.nmclient.NM.SETTING_BRIDGE_SETTING_NAME,
        )
    bridge_setting = nm.bridge.create_setting(bridge_options, con_profile)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    return con_setting.setting, bridge_setting, ipv4_setting, ipv6_setting
