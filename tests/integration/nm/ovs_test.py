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

import pytest

from libnmstate import nm
from libnmstate.nm.nmclient import nmclient_context
from libnmstate.schema import Interface
from libnmstate.schema import OVSBridge as OB

from .testlib import mainloop
from .testlib import MainloopTestError


BRIDGE0 = "brtest0"
ETH1 = "eth1"


@pytest.fixture
def bridge_minimum_config():
    return {OB.CONFIG_SUBTREE: {OB.PORT_SUBTREE: []}}


@pytest.fixture
def bridge_default_config():
    return {
        OB.CONFIG_SUBTREE: {
            OB.OPTIONS_SUBTREE: {
                OB.Options.FAIL_MODE: "",
                OB.Options.MCAST_SNOOPING_ENABLED: False,
                OB.Options.RSTP: False,
                OB.Options.STP: False,
            },
            OB.PORT_SUBTREE: [],
        }
    }


@pytest.mark.xfail(
    raises=(MainloopTestError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_create_and_remove_minimum_config_bridge(
    bridge_minimum_config, bridge_default_config
):
    bridge_desired_state = bridge_minimum_config

    with _bridge_interface(bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        assert bridge_current_state == bridge_default_config
        assert bridge_current_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE] == []

    assert not _get_bridge_current_state()


@pytest.mark.xfail(
    raises=(MainloopTestError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_bridge_with_system_port(eth1_up, bridge_default_config):
    bridge_desired_state = bridge_default_config

    eth1_port = {
        OB.Port.NAME: "eth1",
        # OVS vlan/s are not yet supported.
        # OB.VLAN.MODE: None,
        # OB.VLAN.TAG: 0,
    }

    bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE].append(eth1_port)

    with _bridge_interface(bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state()


@pytest.mark.xfail(
    raises=(MainloopTestError, AssertionError),
    reason="https://bugzilla.redhat.com/1724901",
)
def test_bridge_with_internal_interface(bridge_default_config):
    bridge_desired_state = bridge_default_config

    port_name = "ovs0"
    ovs_port = {OB.Port.NAME: port_name}

    bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE].append(ovs_port)

    with _bridge_interface(bridge_desired_state):
        bridge_current_state = _get_bridge_current_state()
        assert bridge_desired_state == bridge_current_state
        _assert_mac_exists(port_name)

    assert not _get_bridge_current_state()


@contextmanager
def _bridge_interface(state):
    try:
        _create_bridge(state)
        yield
    finally:
        _delete_iface(BRIDGE0)
        for p in state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE]:
            _delete_iface(nm.ovs.PORT_PROFILE_PREFIX + p[OB.Port.NAME])
            _delete_iface(p[OB.Port.NAME])


@nmclient_context
def _get_bridge_current_state():
    state = {}
    nmdev = nm.device.get_device_by_name(BRIDGE0)
    if nmdev:
        devices_info = [
            (dev, nm.device.get_device_common_info(dev))
            for dev in nm.device.list_devices()
        ]
        state = nm.ovs.get_bridge_info(nmdev, devices_info)
    return state


@nmclient_context
def _create_bridge(bridge_desired_state):
    br_options = nm.ovs.translate_bridge_options(bridge_desired_state)
    iface_bridge_settings = _get_iface_bridge_settings(br_options)

    with mainloop():
        _create_bridge_iface(iface_bridge_settings)
        ports_state = bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE]
        for port_state in ports_state:
            _attach_port_to_bridge(port_state)


def _attach_port_to_bridge(port_state):
    port_profile_name = nm.ovs.PORT_PROFILE_PREFIX + port_state[OB.Port.NAME]

    _create_proxy_port(port_profile_name, port_state)
    if _is_internal_interface(port_state[OB.Port.NAME]):
        iface_name = port_state[OB.Port.NAME]
        _create_internal_interface(iface_name, master_name=port_profile_name)
    else:
        _connect_interface(port_profile_name, port_state)


def _is_internal_interface(iface_name):
    dev = nm.device.get_device_by_name(iface_name)
    if not dev:
        return True
    return dev.get_device_type() == nm.nmclient.NM.DeviceType.OVS_INTERFACE


def _create_internal_interface(iface_name, master_name):
    iface_settings = _create_internal_iface_setting(iface_name, master_name)
    iface_con_profile = nm.connection.ConnectionProfile()
    iface_con_profile.create(iface_settings)
    iface_con_profile.add(save_to_disk=False)
    nm.device.activate(connection_id=iface_name)


def _connect_interface(port_profile_name, port_state):
    iface_nmdev = nm.device.get_device_by_name(port_state[OB.Port.NAME])
    curr_iface_con_profile = nm.connection.ConnectionProfile()
    curr_iface_con_profile.import_by_device(iface_nmdev)
    slave_iface_settings = _create_iface_settings(
        curr_iface_con_profile, port_profile_name
    )
    iface_con_profile = nm.connection.ConnectionProfile()
    iface_con_profile.create(slave_iface_settings)
    curr_iface_con_profile.update(iface_con_profile)
    curr_iface_con_profile.commit(nmdev=iface_nmdev)
    nm.device.activate(connection_id=port_state[OB.Port.NAME])


def _create_proxy_port(port_profile_name, port_state):
    port_settings = _create_port_setting(port_state, port_profile_name)
    port_con_profile = nm.connection.ConnectionProfile()
    port_con_profile.create(port_settings)
    port_con_profile.add(save_to_disk=False)
    nm.device.activate(connection_id=port_profile_name)


def _create_bridge_iface(iface_bridge_settings):
    br_con_profile = nm.connection.ConnectionProfile()
    br_con_profile.create(iface_bridge_settings)
    br_con_profile.add(save_to_disk=False)
    nm.device.activate(connection_id=BRIDGE0)


def _create_iface_settings(iface_con_profile, port_master_name):
    iface_con_setting = nm.connection.ConnectionSetting()
    iface_con_setting.import_by_profile(iface_con_profile)
    iface_con_setting.set_master(port_master_name, nm.ovs.PORT_TYPE)
    return (iface_con_setting.setting,)


def _create_port_setting(port_state, port_profile_name):
    iface_con_setting = nm.connection.ConnectionSetting()
    iface_con_setting.create(
        con_name=port_profile_name,
        iface_name=port_profile_name,
        iface_type=nm.ovs.PORT_TYPE,
    )
    iface_con_setting.set_master(BRIDGE0, nm.ovs.BRIDGE_TYPE)
    port_options = nm.ovs.translate_port_options(port_state)
    bridge_port_setting = nm.ovs.create_port_setting(port_options)
    return iface_con_setting.setting, bridge_port_setting


def _create_internal_iface_setting(iface_name, master_name):
    iface_con_setting = nm.connection.ConnectionSetting()
    iface_con_setting.create(
        con_name=iface_name,
        iface_name=iface_name,
        iface_type=nm.ovs.INTERNAL_INTERFACE_TYPE,
    )
    iface_con_setting.set_master(master_name, nm.ovs.PORT_TYPE)
    bridge_internal_iface_setting = nm.ovs.create_interface_setting()
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    return (
        iface_con_setting.setting,
        bridge_internal_iface_setting,
        ipv4_setting,
        ipv6_setting,
    )


@nmclient_context
def _delete_iface(devname):
    nmdev = nm.device.get_device_by_name(devname)
    with mainloop():
        if nmdev:
            nm.device.delete(nmdev)
            if nmdev.get_device_type() in (
                nm.nmclient.NM.DeviceType.OVS_BRIDGE,
                nm.nmclient.NM.DeviceType.OVS_PORT,
                nm.nmclient.NM.DeviceType.OVS_INTERFACE,
            ):
                nm.device.delete_device(nmdev)
        else:
            con_profile = nm.connection.ConnectionProfile()
            con_profile.con_id = devname
            con_profile.delete()


def _get_iface_bridge_settings(bridge_options):
    bridge_con_setting = nm.connection.ConnectionSetting()
    bridge_con_setting.create(
        con_name=BRIDGE0,
        iface_name=BRIDGE0,
        iface_type=nm.nmclient.NM.SETTING_OVS_BRIDGE_SETTING_NAME,
    )
    bridge_setting = nm.ovs.create_bridge_setting(bridge_options)
    return bridge_con_setting.setting, bridge_setting


def _assert_mac_exists(ifname):
    state = {}
    nmdev = nm.device.get_device_by_name(ifname)
    if nmdev:
        state = nm.wired.get_info(nmdev)
    assert state.get(Interface.MAC)
