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


@contextmanager
def _bridge_interface(state):
    try:
        _create_bridge(state)
        yield
    finally:
        _delete_iface(BRIDGE0)


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


def _create_bridge_iface(iface_bridge_settings):
    br_con_profile = nm.connection.create_profile(iface_bridge_settings)
    nm.connection.add_profile(br_con_profile, save_to_disk=False)
    nm.device.activate(connection_id=BRIDGE0)


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
