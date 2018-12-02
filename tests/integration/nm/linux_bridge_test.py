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

import pytest

from libnmstate import nm
from libnmstate.schema import LinuxBridge as LB

from .testlib import mainloop


BRIDGE0 = 'brtest0'
ETH1 = 'eth1'


@pytest.fixture
def bridge_minimum_config():
    return {
        LB.CONFIG_SUBTREE: {
            LB.PORT_SUBTREE: []
        }
    }


@pytest.fixture
def bridge_default_config():
    return {
        LB.CONFIG_SUBTREE: {
            LB.GROUP_FORWARD_MASK: 0,
            LB.MAC_AGEING_TIME: 300,
            LB.MULTICAST_SNOOPING: True,
            LB.STP_SUBTREE: {
                LB.STP_ENABLED: True,
                LB.STP_FORWARD_DELAY: 15,
                LB.STP_HELLO_TIME: 2,
                LB.STP_MAX_AGE: 20,
                LB.STP_PRIORITY: 32768
            },
            LB.PORT_SUBTREE: []
        }
    }


def test_create_and_remove_minimum_config_bridge(bridge_minimum_config):
    bridge_desired_state = bridge_minimum_config

    with _bridge_interface(bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_current_state
        assert not bridge_current_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]

    assert not _get_bridge_current_state()


def test_create_and_remove_bridge(eth1_up, bridge_default_config):
    bridge_desired_state = bridge_default_config

    eth1_port = {
        LB.PORT_NAME: 'eth1',
        LB.PORT_STP_PRIORITY: 32,
        LB.PORT_STP_HAIRPIN_MODE: False,
        LB.PORT_STP_PATH_COST: 100
    }

    bridge_desired_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE].append(eth1_port)

    with _bridge_interface(bridge_desired_state):

        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


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


def _create_bridge(bridge_desired_state):
    iface_bridge_settings = _get_iface_bridge_settings(bridge_desired_state)

    with mainloop():
        _create_bridge_iface(iface_bridge_settings)
        ports_state = bridge_desired_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE]
        for port_state in ports_state:
            _attach_port_to_bridge(port_state)


def _attach_port_to_bridge(port_state):
    eth1_nmdev = nm.device.get_device_by_name(port_state['name'])
    curr_port_con_profile = nm.connection.get_device_connection(eth1_nmdev)
    iface_port_settings = _get_iface_port_settings(port_state,
                                                   curr_port_con_profile)
    port_con_profile = nm.connection.create_profile(iface_port_settings)
    nm.connection.update_profile(curr_port_con_profile, port_con_profile)
    nm.connection.commit_profile(curr_port_con_profile, nmdev=eth1_nmdev)
    nm.device.activate(connection_id=port_state[LB.PORT_NAME])


def _create_bridge_iface(iface_bridge_settings):
    br_con_profile = nm.connection.create_profile(iface_bridge_settings)
    nm.connection.add_profile(br_con_profile, save_to_disk=False)
    nm.device.activate(connection_id=BRIDGE0)


def _get_iface_port_settings(port_state, port_con_profile):
    port_con_setting = nm.connection.duplicate_settings(port_con_profile)

    nm.connection.set_master_setting(port_con_setting, BRIDGE0, 'bridge')
    bridge_port_setting = nm.bridge.create_port_setting(port_state,
                                                        port_con_profile)
    return port_con_setting, bridge_port_setting


def _delete_iface(devname):
    nmdev = nm.device.get_device_by_name(devname)
    with mainloop():
        nm.device.deactivate(nmdev)
        nm.device.delete(nmdev)


def _get_iface_bridge_settings(bridge_desired_state):
    bridge_con_setting = nm.connection.create_setting(
        con_name=BRIDGE0,
        iface_name=BRIDGE0,
        iface_type=nm.nmclient.NM.SETTING_BRIDGE_SETTING_NAME,
    )
    bridge_setting = nm.bridge.create_setting(bridge_desired_state,
                                              base_con_profile=None)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    return bridge_con_setting, bridge_setting, ipv4_setting, ipv6_setting
