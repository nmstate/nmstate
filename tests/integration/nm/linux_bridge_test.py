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

from libnmstate import nm
from libnmstate import schema
from libnmstate.schema import LinuxBridge as LB

from .testlib import mainloop_run


BRIDGE0 = 'brtest0'


def test_create_and_remove_minimum_config_bridge():
    bridge_desired_state = {LB.CONFIG_SUBTREE: {LB.PORT_SUBTREE: []}}

    with _bridge_interface(bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_current_state
        assert not bridge_current_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]

    assert not _get_bridge_current_state()


def test_create_and_remove_bridge(port0_up):
    port_name = port0_up[schema.Interface.KEY][0][schema.Interface.NAME]
    bridge_desired_state = _create_bridge_config((port_name,))
    with _bridge_interface(bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


def _create_bridge_config(ports):
    ports_states = _create_bridge_ports_config(ports)
    return {
        LB.CONFIG_SUBTREE: {
            LB.OPTIONS_SUBTREE: {
                LB.GROUP_FORWARD_MASK: 0,
                LB.MAC_AGEING_TIME: 300,
                LB.MULTICAST_SNOOPING: True,
                LB.STP_SUBTREE: {
                    LB.STP_ENABLED: True,
                    LB.STP_FORWARD_DELAY: 15,
                    LB.STP_HELLO_TIME: 2,
                    LB.STP_MAX_AGE: 20,
                    LB.STP_PRIORITY: 32768,
                },
            },
            LB.PORT_SUBTREE: ports_states,
        }
    }


def _create_bridge_ports_config(ports):
    return [
        {
            LB.PORT_NAME: port,
            LB.PORT_STP_PRIORITY: 32,
            LB.PORT_STP_HAIRPIN_MODE: False,
            LB.PORT_STP_PATH_COST: 100,
        }
        for port in ports
    ]


@contextmanager
def _bridge_interface(state):
    try:
        _create_bridge(state)
        yield
    finally:
        _delete_iface(BRIDGE0)
        for p in state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]:
            _delete_iface(p[LB.PORT_NAME])


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
    nm.device.activate(connection_id=port_state[LB.PORT_NAME])


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


def _create_iface_bridge_settings(bridge_options):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=BRIDGE0,
        iface_name=BRIDGE0,
        iface_type=nm.nmclient.NM.SETTING_BRIDGE_SETTING_NAME,
    )
    bridge_setting = nm.bridge.create_setting(
        bridge_options, base_con_profile=None
    )
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    return con_setting.setting, bridge_setting, ipv4_setting, ipv6_setting
