#
# Copyright (c) 2019 Red Hat, Inc.
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

from distutils.version import StrictVersion

from libnmstate import nm
from libnmstate.schema import Interface
from libnmstate.schema import VXLAN

from .testlib import context


def test_create_and_remove_vxlan(eth1_up):
    vxlan_desired_state = _create_vxlan_state(eth1_up)
    with _vxlan_interface(vxlan_desired_state):
        vxlan_name = _vxlan_ifname(vxlan_desired_state)
        vxlan_current_state = _get_vxlan_current_state(vxlan_name)
        assert vxlan_desired_state == vxlan_current_state

    assert not _get_vxlan_current_state(vxlan_name)


def _nm_version():
    with context() as ctx:
        return nm.nmclient.nm_version(ctx.client)


@pytest.mark.xfail(
    condition=StrictVersion(_nm_version()) < StrictVersion("1.20.6"),
    strict=True,
    reason="https://bugzilla.redhat.com/show_bug.cgi?id=1768388",
)
def test_read_destination_port_from_libnm(eth1_up):
    vxlan_desired_state = _create_vxlan_state(eth1_up)
    with _vxlan_interface(vxlan_desired_state):
        vxlan_name = _vxlan_ifname(vxlan_desired_state)
        vxlan_device = _get_vxlan_device(vxlan_name)
        assert vxlan_device is not None
        obtained_destination_port = vxlan_device.props.dst_port
        expected_destination_port = vxlan_desired_state[VXLAN.CONFIG_SUBTREE][
            VXLAN.DESTINATION_PORT
        ]
        assert obtained_destination_port == expected_destination_port


def _create_vxlan_state(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    return {
        VXLAN.CONFIG_SUBTREE: {
            VXLAN.ID: 201,
            VXLAN.BASE_IFACE: ifname,
            VXLAN.REMOTE: "192.168.1.18",
            VXLAN.DESTINATION_PORT: 4789,
        }
    }


@contextmanager
def _vxlan_interface(state):
    try:
        with context() as ctx:
            _create_vxlan(ctx, state)
        yield state
    finally:
        with context() as ctx:
            _delete_vxlan(ctx, _vxlan_ifname(state))


def _create_vxlan(ctx, vxlan_desired_state):
    ifname = _vxlan_ifname(vxlan_desired_state)
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=ifname,
        iface_name=ifname,
        iface_type=nm.nmclient.NM.SETTING_VXLAN_SETTING_NAME,
    )
    vxlan_setting = nm.vxlan.create_setting(
        vxlan_desired_state, base_con_profile=None
    )
    ipv4_setting = nm.ipv4.create_setting(ctx, {}, None)
    ipv6_setting = nm.ipv6.create_setting(ctx, {}, None)
    con_profile = nm.connection.ConnectionProfile()
    con_profile.create(
        (con_setting.setting, vxlan_setting, ipv4_setting, ipv6_setting)
    )
    con_profile.add(save_to_disk=False)
    nm.device.activate(ctx, connection_id=ifname)


def _delete_vxlan(ctx, devname):
    nmdev = nm.device.get_device_by_name(ctx, devname)
    nm.device.deactivate(ctx, nmdev)
    nm.device.delete(ctx, nmdev)
    nm.device.delete_device(ctx, nmdev)


def _get_vxlan_current_state(ctx, ifname):
    with context() as ctx:
        nmdev = _get_vxlan_device(ctx, ifname)
        return nm.vxlan.get_info(ctx, nmdev) if nmdev else {}


def _get_vxlan_device(ctx, ifname):
    return nm.device.get_device_by_name(ctx, ifname)


def _vxlan_ifname(state):
    return (
        state[VXLAN.CONFIG_SUBTREE][VXLAN.BASE_IFACE]
        + "."
        + str(state[VXLAN.CONFIG_SUBTREE][VXLAN.ID])
    )
