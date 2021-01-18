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

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import VLAN

from ..testlib import assertlib
from ..testlib import statelib
from ..testlib import cmdlib
from ..testlib.ovslib import Bridge


BRIDGE0 = "brtest0"
IFACE0 = "ovstest0"


@pytest.fixture
def bridge_with_ports(eth1_up):
    bridge = Bridge(BRIDGE0)
    bridge.add_system_port("eth1")
    bridge.add_internal_port(IFACE0, ipv4_state={InterfaceIPv4.ENABLED: False})
    with bridge.create():
        yield bridge


@pytest.fixture
def ovs_unmanaged_bridge():
    cmdlib.exec_cmd(f"ovs-vsctl add-br {BRIDGE0}".split())
    yield
    cmdlib.exec_cmd(f"ovs-vsctl del-br {BRIDGE0}".split())


@pytest.mark.tier1
def test_do_not_show_unmanaged_ovs_bridge(ovs_unmanaged_bridge):
    # The output should only contains the OVS internal interface
    ovs_internal_iface = statelib.show_only((BRIDGE0,))[Interface.KEY][0]
    assert ovs_internal_iface[Interface.TYPE] == InterfaceType.OVS_INTERFACE


@pytest.fixture
def nmcli_created_ovs_bridge_with_same_name_iface():
    cmdlib.exec_cmd(
        "nmcli c add type ovs-bridge connection.id "
        f"{BRIDGE0} ifname {BRIDGE0}".split()
    )

    cmdlib.exec_cmd(
        "nmcli c add type ovs-port connection.id "
        f"{IFACE0} ifname {IFACE0} "
        f"connection.master {BRIDGE0} connection.slave-type ovs-bridge".split()
    )

    cmdlib.exec_cmd(
        "nmcli c add type ovs-interface connection.id "
        f"{IFACE0} ifname {IFACE0} "
        f"ipv4.method disabled ipv6.method disabled "
        f"connection.master {IFACE0} connection.slave-type ovs-port".split()
    )

    yield
    cmdlib.exec_cmd(f"ovs-vsctl del-br {BRIDGE0} {IFACE0} ".split())


@pytest.mark.tier1
def test_create_vlan_over_existing_ovs_iface_with_use_same_name_as_bridge(
    nmcli_created_ovs_bridge_with_same_name_iface,
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "vlan101",
                Interface.TYPE: InterfaceType.VLAN,
                VLAN.CONFIG_SUBTREE: {VLAN.ID: 101, VLAN.BASE_IFACE: IFACE0},
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state_match(desired_state)


class _OvsProfileStillExists(Exception):
    pass


@pytest.mark.tier1
def test_remove_ovs_internal_iface_got_port_profile_removed(bridge_with_ports):
    for ovs_iface_name in bridge_with_ports.ports_names:
        active_profile_names, active_profile_uuids = _get_nm_active_profiles()
        assert ovs_iface_name in active_profile_names
        ovs_port_profile_uuid = _get_ovs_port_profile_uuid_of_ovs_interface(
            ovs_iface_name
        )
        assert ovs_port_profile_uuid
        assert ovs_port_profile_uuid in active_profile_uuids
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ovs_iface_name,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )

        rc, output, _ = cmdlib.exec_cmd(
            f"nmcli c show {ovs_port_profile_uuid}".split(" "),
        )
        if rc == 0:
            raise _OvsProfileStillExists(
                f"{ovs_port_profile_uuid} still exists: {output}"
            )


def _get_nm_active_profiles():
    all_profile_names_output = cmdlib.exec_cmd(
        "nmcli -g NAME connection show --active".split(" "), check=True
    )[1]
    all_profile_uuids_output = cmdlib.exec_cmd(
        "nmcli -g UUID connection show --active".split(" "), check=True
    )[1]
    return (
        all_profile_names_output.split("\n"),
        all_profile_uuids_output.split("\n"),
    )


def _get_ovs_port_profile_uuid_of_ovs_interface(iface_name):
    ovs_port_uuid = cmdlib.exec_cmd(
        f"nmcli -g connection.master connection show {iface_name}".split(" "),
        check=True,
    )[1].strip()
    cmdlib.exec_cmd(
        f"nmcli -g connection.id connection show {ovs_port_uuid}".split(" "),
        check=True,
    )
    return ovs_port_uuid
