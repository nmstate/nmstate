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
import time

import pytest

import libnmstate
from libnmstate import nm
from libnmstate.nm.common import NM
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import OVSBridge as OB
from libnmstate.schema import VLAN

from .testlib import main_context
from ..testlib import cmdlib
from ..testlib import assertlib
from ..testlib.retry import retry_till_true_or_timeout


BRIDGE0 = "brtest0"
ETH1 = "eth1"
ETH2 = "eth2"
BOND0 = "bond0"
OVS_DUP_NAME = "br-ex"

VERIFY_RETRY_TMO = 5


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


def test_create_and_remove_minimum_config_bridge(
    bridge_minimum_config, bridge_default_config, nm_plugin
):
    bridge_desired_state = bridge_minimum_config

    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_current_state == bridge_default_config
        assert bridge_current_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE] == []

    assert not _get_bridge_current_state(nm_plugin)


def test_bridge_with_system_port(eth1_up, bridge_default_config, nm_plugin):
    bridge_desired_state = bridge_default_config

    eth1_port = {
        OB.Port.NAME: "eth1",
        OB.Port.VLAN_SUBTREE: {
            OB.Port.Vlan.MODE: OB.Port.Vlan.Mode.ACCESS,
            OB.Port.Vlan.TAG: 2,
        },
    }

    bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE].append(eth1_port)

    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state(nm_plugin)


def test_bridge_with_internal_interface(bridge_default_config, nm_plugin):
    bridge_desired_state = bridge_default_config

    port_name = "ovs0"
    ovs_port = {OB.Port.NAME: port_name}

    bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE].append(ovs_port)

    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_desired_state == bridge_current_state
        _assert_mac_exists(nm_plugin.context, port_name)

    assert not _get_bridge_current_state(nm_plugin)


@pytest.mark.parametrize(
    "mode",
    [
        OB.Port.LinkAggregation.Mode.ACTIVE_BACKUP,
        OB.Port.LinkAggregation.Mode.BALANCE_SLB,
        OB.Port.LinkAggregation.Mode.BALANCE_TCP,
        OB.Port.LinkAggregation.Mode.LACP,
    ],
)
def test_bridge_with_bond_and_two_slaves(
    port0_up, port1_up, bridge_default_config, mode, nm_plugin
):
    slave0_name = port0_up[Interface.KEY][0][Interface.NAME]
    slave1_name = port1_up[Interface.KEY][0][Interface.NAME]
    bridge_desired_state = bridge_default_config

    port_name = "bond0"
    LAG = OB.Port.LinkAggregation
    port_state = {
        OB.Port.NAME: port_name,
        OB.Port.LINK_AGGREGATION_SUBTREE: {
            LAG.MODE: mode,
            LAG.SLAVES_SUBTREE: [
                {LAG.Slave.NAME: slave0_name},
                {LAG.Slave.NAME: slave1_name},
            ],
        },
    }
    bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE].append(port_state)

    with _bridge_interface(nm_plugin.context, bridge_desired_state):
        bridge_current_state = _get_bridge_current_state(nm_plugin)
        assert bridge_desired_state == bridge_current_state

    assert not _get_bridge_current_state(nm_plugin)


@contextmanager
def _bridge_interface(ctx, state):
    try:
        _create_bridge(ctx, state)
        yield
    finally:
        _delete_iface(ctx, BRIDGE0)
        for p in state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE]:
            if not p.get(OB.Port.LINK_AGGREGATION_SUBTREE):
                _delete_iface(
                    ctx, nm.ovs.PORT_PROFILE_PREFIX + p[OB.Port.NAME]
                )
            _delete_iface(ctx, p[OB.Port.NAME])


def _get_bridge_current_state(nm_plugin):
    nm_plugin.refresh_content()
    state = {}
    nmdev = nm_plugin.context.get_nm_dev(BRIDGE0)
    if nmdev:
        devices_info = [
            (dev, nm.device.get_device_common_info(dev))
            for dev in nm.device.list_devices(nm_plugin.context.client)
        ]
        ovs_info = nm.ovs.get_ovs_info(nm_plugin.context, nmdev, devices_info)
        if ovs_info:
            state[OB.CONFIG_SUBTREE] = ovs_info
    return state


def _create_bridge(ctx, bridge_desired_state):
    bridge_state = bridge_desired_state.get(OB.CONFIG_SUBTREE, {})
    br_options = bridge_state.get(OB.OPTIONS_SUBTREE, {})
    iface_bridge_settings = _get_iface_bridge_settings(br_options)

    with main_context(ctx):
        _create_bridge_iface(ctx, iface_bridge_settings)
        ports_state = bridge_desired_state[OB.CONFIG_SUBTREE][OB.PORT_SUBTREE]
        for port_state in ports_state:
            _attach_port_to_bridge(ctx, port_state)


def _attach_port_to_bridge(ctx, port_state):
    port_name = port_state[OB.Port.NAME]
    lag_state = port_state.get(OB.Port.LINK_AGGREGATION_SUBTREE)
    if lag_state:
        port_profile_name = port_name
    else:
        port_profile_name = nm.ovs.PORT_PROFILE_PREFIX + port_name

    _create_proxy_port(ctx, port_profile_name, port_state)
    if lag_state:
        slaves = [
            slave
            for slave in lag_state[OB.Port.LinkAggregation.SLAVES_SUBTREE]
        ]
        for slave in slaves:
            _connect_interface(ctx, port_profile_name, slave)
    elif _is_internal_interface(ctx, port_name):
        iface_name = port_name
        _create_internal_interface(
            ctx, iface_name, master_name=port_profile_name
        )
    else:
        _connect_interface(ctx, port_profile_name, port_state)


def _is_internal_interface(ctx, iface_name):
    dev = ctx.get_nm_dev(iface_name)
    if not dev:
        return True
    return dev.get_device_type() == NM.DeviceType.OVS_INTERFACE


def _create_internal_interface(ctx, iface_name, master_name):
    iface_settings = _create_internal_iface_setting(iface_name, master_name)
    iface_con_profile = nm.connection.ConnectionProfile(ctx)
    iface_con_profile.create(iface_settings)
    iface_con_profile.add()
    ctx.wait_all_finish()
    nm.device.activate(ctx, connection_id=iface_name)


def _connect_interface(ctx, port_profile_name, port_state):
    iface_nmdev = ctx.get_nm_dev(port_state[OB.Port.NAME])
    curr_iface_con_profile = nm.connection.ConnectionProfile(ctx)
    curr_iface_con_profile.import_by_device(iface_nmdev)
    slave_iface_settings = _create_iface_settings(
        curr_iface_con_profile, port_profile_name
    )
    iface_con_profile = nm.connection.ConnectionProfile(ctx)
    iface_con_profile.create(slave_iface_settings)
    curr_iface_con_profile.update(iface_con_profile)
    ctx.wait_all_finish()
    nm.device.activate(ctx, connection_id=port_state[OB.Port.NAME])


def _create_proxy_port(ctx, port_profile_name, port_state):
    port_settings = _create_port_setting(port_state, port_profile_name)
    port_con_profile = nm.connection.ConnectionProfile(ctx)
    port_con_profile.create(port_settings)
    port_con_profile.add()
    ctx.wait_all_finish()
    nm.device.activate(ctx, connection_id=port_profile_name)


def _create_bridge_iface(ctx, iface_bridge_settings):
    br_con_profile = nm.connection.ConnectionProfile(ctx)
    br_con_profile.create(iface_bridge_settings)
    br_con_profile.add()
    ctx.wait_all_finish()
    nm.device.activate(ctx, connection_id=BRIDGE0)


def _create_iface_settings(iface_con_profile, port_master_name):
    iface_con_setting = nm.connection.ConnectionSetting()
    iface_con_setting.import_by_profile(iface_con_profile)
    iface_con_setting.set_master(port_master_name, InterfaceType.OVS_PORT)
    return (iface_con_setting.setting,)


def _create_port_setting(port_state, port_profile_name):
    iface_con_setting = nm.connection.ConnectionSetting()
    iface_con_setting.create(
        con_name=port_profile_name,
        iface_name=port_profile_name,
        iface_type=InterfaceType.OVS_PORT,
    )
    iface_con_setting.set_master(BRIDGE0, InterfaceType.OVS_BRIDGE)
    bridge_port_setting = nm.ovs.create_port_setting(port_state)
    return iface_con_setting.setting, bridge_port_setting


def _create_internal_iface_setting(iface_name, master_name):
    iface_con_setting = nm.connection.ConnectionSetting()
    iface_con_setting.create(
        con_name=iface_name,
        iface_name=iface_name,
        iface_type=InterfaceType.OVS_INTERFACE,
    )
    iface_con_setting.set_master(master_name, InterfaceType.OVS_PORT)
    bridge_internal_iface_setting = nm.ovs.create_interface_setting(None)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    settings = [
        iface_con_setting.setting,
        ipv4_setting,
        ipv6_setting,
    ]
    settings.extend(bridge_internal_iface_setting)

    return settings


def _delete_iface(ctx, devname):
    nmdev = ctx.get_nm_dev(devname)
    with main_context(ctx):
        if nmdev:
            nm.device.delete(ctx, nmdev)
            if nmdev.get_device_type() in (
                NM.DeviceType.OVS_BRIDGE,
                NM.DeviceType.OVS_PORT,
                NM.DeviceType.OVS_INTERFACE,
            ):
                nm.device.delete_device(ctx, nmdev)
        else:
            con_profile = nm.connection.ConnectionProfile(ctx)
            con_profile.con_id = devname
            con_profile.delete()


def _get_iface_bridge_settings(bridge_options):
    bridge_con_setting = nm.connection.ConnectionSetting()
    bridge_con_setting.create(
        con_name=BRIDGE0,
        iface_name=BRIDGE0,
        iface_type=NM.SETTING_OVS_BRIDGE_SETTING_NAME,
    )
    bridge_setting = nm.ovs.create_bridge_setting(bridge_options)
    return bridge_con_setting.setting, bridge_setting


def _assert_mac_exists(ctx, ifname):
    state = {}
    nmdev = ctx.get_nm_dev(ifname)
    if nmdev:
        state = nm.wired.get_info(nmdev)
    assert state.get(Interface.MAC)


@pytest.fixture
def ovs_bridge_over_bond_system_iface_with_same_name(eth1_up, eth2_up):
    cmdlib.exec_cmd(
        "nmcli c add type ovs-bridge connection.id "
        f"{BRIDGE0} ifname {BRIDGE0}".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"nmcli c add type ovs-port connection.id ovs-port-{BOND0} "
        f"ifname {BOND0} connection.master {BRIDGE0} "
        "connection.slave-type ovs-bridge".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"nmcli c add type bond connection.id ovs-iface-{BOND0} "
        f"ifname {BOND0} ipv4.method disabled ipv6.method disabled "
        f"connection.master {BOND0} connection.slave-type ovs-port".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"nmcli c add type ethernet connection.id {ETH1} ifname {ETH1} "
        f"connection.master {BOND0} connection.slave-type bond".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        f"nmcli c add type ethernet connection.id {ETH2} ifname {ETH2} "
        f"connection.master {BOND0} connection.slave-type bond".split(),
        check=True,
    )
    yield
    cmdlib.exec_cmd(
        f"nmcli c del ovs-port-{BOND0} {BRIDGE0} ovs-iface-{BOND0} "
        f"{ETH1} {ETH2}".split(),
        check=False,
    )
    # Wait a little bit for NM to remove above interfaces, so that
    # later clean up function does not hit into race problem
    time.sleep(1)


def _nmcli_ovs_bridge_with_ipv4_dns():
    nmcli_ovs_interface = (
        "nmcli",
        "connection",
        "add",
        "type",
        "ovs-interface",
        "slave-type",
        "ovs-port",
        "conn.interface",
        "br-ex",
        "master",
        "ovs-port-br-ex",
        "con-name",
        "ovs-if-br-ex",
        "ipv4.method",
        "manual",
        "ipv4.addr",
        "192.0.2.2/24",
        "ipv4.dns",
        "192.0.2.1",
        "ipv4.routes",
        "0.0.0.0/0 192.0.2.1",
    )
    cmdlib.exec_cmd(nmcli_ovs_interface, check=True)


def _verify_ovs_activated(ovs_name):
    ret, out, err = cmdlib.exec_cmd(
        f"nmcli --field GENERAL.STATE device show {ovs_name}".split(),
        check=True,
    )
    connected = "connected" in out
    ret, out, err = cmdlib.exec_cmd(
        f"nmcli --field IP4.ADDRESS device show {ovs_name}".split(),
        check=True,
    )
    ipv4_configured = "192.0.2.2/24" in out
    ret, out, err = cmdlib.exec_cmd(
        f"nmcli --field IP4.ROUTE device show {ovs_name}".split(), check=True,
    )
    route_configured = "0.0.0.0/0" in out
    return connected and ipv4_configured and route_configured


@pytest.fixture
def ovs_bridge_first_and_ovs_interface_with_same_name_ipv4():
    # The order on this function is important. The OVS bridge must be defined
    # before the OVS interface.
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-port conn.interface br-ex master br-ex "
        "con-name ovs-port-br-ex".split(),
        check=True,
    )
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-bridge con-name br-ex conn.interface "
        "br-ex".split(),
        check=True,
    )
    _nmcli_ovs_bridge_with_ipv4_dns()
    # Wait a little bit for NM to activate above interfaces to do not hit race
    # problems.
    assert retry_till_true_or_timeout(
        VERIFY_RETRY_TMO, _verify_ovs_activated, OVS_DUP_NAME
    )
    yield
    cmdlib.exec_cmd(
        "nmcli connection del ovs-port-br-ex br-ex ovs-if-br-ex".split(),
        check=True,
    )


@pytest.fixture
def ovs_interface_first_and_ovs_bridge_with_same_name_ipv4():
    # The order on this function is important. The OVS interface must be
    # defined before the OVS bridge.
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-port conn.interface br-ex master br-ex "
        "con-name ovs-port-br-ex".split(),
        check=True,
    )
    _nmcli_ovs_bridge_with_ipv4_dns()
    cmdlib.exec_cmd(
        "nmcli connection add type ovs-bridge con-name br-ex conn.interface "
        "br-ex".split(),
        check=True,
    )
    # Wait a little bit for NM to activate above interfaces to do not hit race
    # problems.
    assert retry_till_true_or_timeout(
        VERIFY_RETRY_TMO, _verify_ovs_activated, OVS_DUP_NAME
    )
    yield
    cmdlib.exec_cmd(
        "nmcli connection del ovs-port-br-ex br-ex ovs-if-br-ex".split(),
        check=True,
    )


@pytest.mark.tier1
def test_create_vlan_over_ovs_system_interface_bond_with_same_name(
    ovs_bridge_over_bond_system_iface_with_same_name,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "vlan101",
                Interface.TYPE: InterfaceType.VLAN,
                Interface.STATE: InterfaceState.UP,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: BOND0},
            }
        ]
    }
    try:
        libnmstate.apply(desired_state)
        assertlib.assert_state_match(desired_state)
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: "vlan101",
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )


@pytest.mark.tier1
def test_modify_state_with_ovs_dup_name_ovs_bridge_first_with_ipv4_dns(
    ovs_bridge_first_and_ovs_interface_with_same_name_ipv4,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ETH1,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)


@pytest.mark.tier1
def test_modify_state_with_ovs_dup_name_ovs_interface_first_with_ipv4_dns(
    ovs_interface_first_and_ovs_bridge_with_same_name_ipv4,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ETH1,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)
