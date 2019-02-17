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

import pytest

from libnmstate import nm
from libnmstate.schema import OVSBridge as OB

from .testlib import mainloop


BRIDGE0 = 'brtest0'
ETH1 = 'eth1'


@pytest.fixture
def bridge_minimum_config():
    return {
        OB.CONFIG_SUBTREE: {
            OB.PORT_SUBTREE: []
        }
    }


@pytest.fixture
def bridge_default_config():
    return {
        OB.CONFIG_SUBTREE: {
            OB.OPTIONS_SUBTREE: {
                OB.FAIL_MODE: '',
                OB.MCAST_SNOOPING_ENABLED: False,
                OB.RSTP: False,
                OB.STP: False
            },
            OB.PORT_SUBTREE: []
        }
    }


def test_create_and_remove_minimum_config_bridge(bridge_minimum_config,
                                                 bridge_default_config):
    bridge_desired_state = bridge_minimum_config

    with _bridge_interface(bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        assert bridge_current_state == bridge_default_config
        assert bridge_current_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE] == []

    assert not _get_bridge_current_state()


def test_bridge_with_system_port(eth1_up, bridge_default_config):
    bridge_desired_state = bridge_default_config

    eth1_port = {
        OB.PORT_NAME: 'eth1',
        OB.PORT_TYPE: 'system',
        # OVS vlan/s are not yet supported.
        # OB.PORT_VLAN_MODE: None,
        # OB.PORT_ACCESS_TAG: 0,
    }

    bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE].append(eth1_port)

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
        for p in state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE]:
            _delete_iface(nm.ovs.PORT_PROFILE_PREFIX + p[OB.PORT_NAME])
            _delete_iface(p[OB.PORT_NAME])


def _get_bridge_current_state():
    nm.nmclient.client(refresh=True)
    state = {}
    nmdev = nm.device.get_device_by_name(BRIDGE0)
    if nmdev:
        devices_info = [(dev, nm.device.get_device_common_info(dev))
                        for dev in nm.device.list_devices()]
        state = nm.ovs.get_bridge_info(nmdev, devices_info)
    return state


def _create_bridge(bridge_desired_state):
    br_options = nm.ovs.translate_bridge_options(bridge_desired_state)
    iface_bridge_settings = _get_iface_bridge_settings(br_options)

    with mainloop():
        _create_bridge_iface(iface_bridge_settings)
        ports_state = bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE]
        for port_state in ports_state:
            _attach_port_to_bridge(port_state)


def _attach_port_to_bridge(port_state):
    port_profile_name = nm.ovs.PORT_PROFILE_PREFIX + port_state[OB.PORT_NAME]

    _create_proxy_port(port_profile_name, port_state)
    _connect_interface(port_profile_name, port_state)


def _connect_interface(port_profile_name, port_state):
    iface_nmdev = nm.device.get_device_by_name(port_state[OB.PORT_NAME])
    curr_iface_con_profile = nm.connection.get_device_connection(iface_nmdev)
    slave_iface_settings = _create_iface_settings(curr_iface_con_profile,
                                                  port_profile_name)
    iface_con_profile = nm.connection.create_profile(slave_iface_settings)
    nm.connection.update_profile(curr_iface_con_profile, iface_con_profile)
    nm.connection.commit_profile(curr_iface_con_profile, nmdev=iface_nmdev)
    nm.device.activate(connection_id=port_state[OB.PORT_NAME])


def _create_proxy_port(port_profile_name, port_state):
    port_settings = _create_port_setting(port_state, port_profile_name)
    port_con_profile = nm.connection.create_profile(port_settings)
    nm.connection.add_profile(port_con_profile, save_to_disk=False)
    nm.device.activate(connection_id=port_profile_name)


def _create_bridge_iface(iface_bridge_settings):
    br_con_profile = nm.connection.create_profile(iface_bridge_settings)
    nm.connection.add_profile(br_con_profile, save_to_disk=False)
    nm.device.activate(connection_id=BRIDGE0)


def _create_iface_settings(iface_con_profile, port_master_name):
    iface_con_setting = nm.connection.duplicate_settings(iface_con_profile)
    nm.connection.set_master_setting(iface_con_setting,
                                     port_master_name,
                                     nm.ovs.PORT_TYPE)
    return (iface_con_setting,)


def _create_port_setting(port_state, port_profile_name):
    iface_con_setting = nm.connection.create_setting(
        con_name=port_profile_name,
        iface_name=port_profile_name,
        iface_type=nm.ovs.PORT_TYPE
    )
    nm.connection.set_master_setting(iface_con_setting,
                                     BRIDGE0,
                                     nm.ovs.BRIDGE_TYPE)
    port_options = nm.ovs.translate_port_options(port_state)
    bridge_port_setting = nm.ovs.create_port_setting(port_options)
    return iface_con_setting, bridge_port_setting


def _delete_iface(devname):
    nmdev = nm.device.get_device_by_name(devname)
    with mainloop():
        nm.device.delete(nmdev)


def _get_iface_bridge_settings(bridge_options):
    bridge_con_setting = nm.connection.create_setting(
        con_name=BRIDGE0,
        iface_name=BRIDGE0,
        iface_type=nm.nmclient.NM.SETTING_OVS_BRIDGE_SETTING_NAME,
    )
    bridge_setting = nm.ovs.create_bridge_setting(bridge_options)
    return bridge_con_setting, bridge_setting
