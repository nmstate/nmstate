#
# Copyright (c) 2019-2021 Red Hat, Inc.
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

import os
import time

import pytest

import libnmstate

from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface
from libnmstate.schema import VXLAN

from .testlib import assertlib
from .testlib.bondlib import bond_interface
from .testlib.cmdlib import RC_SUCCESS
from .testlib.cmdlib import exec_cmd
from .testlib.cmdlib import format_exec_cmd_result
from .testlib.env import is_k8s
from .testlib.env import nm_major_minor_version
from .testlib.vxlan import VxlanState
from .testlib.vxlan import vxlan_interfaces
from .testlib.vxlan import vxlans_absent
from .testlib.vxlan import vxlans_down
from .testlib.vxlan import vxlans_up

VXLAN1_ID = 201
VXLAN2_ID = 202


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_add_and_remove_vxlan(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_add_and_remove_two_vxlans_on_same_iface(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1"),
        VxlanState(id=VXLAN2_ID, base_if=ifname, remote="192.168.100.2"),
    ) as desired_state:
        assertlib.assert_state(desired_state)

    vxlan_interfaces_name = (
        i[Interface.NAME] for i in desired_state[Interface.KEY]
    )
    assertlib.assert_absent(vxlan_interfaces_name)


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=AssertionError,
    strict=False,
)
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_rollback_for_vxlans(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    current_state = libnmstate.show()
    desired_state = vxlans_up(
        [
            VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1"),
            VxlanState(id=VXLAN2_ID, base_if=ifname, remote="192.168.100.2"),
        ]
    )
    desired_state[Interface.KEY][1]["invalid_key"] = "foo"
    with pytest.raises((NmstateVerificationError, NmstateValueError)):
        libnmstate.apply(desired_state)

    time.sleep(5)  # Give some time for NetworkManager to rollback
    current_state_after_apply = libnmstate.show()
    assert current_state == current_state_after_apply


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_set_vxlan_iface_down(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    vxlan = VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    with vxlan_interfaces(vxlan):
        desired_state = vxlans_down([vxlan])
        libnmstate.apply(desired_state)
        assertlib.assert_absent(vxlan.name)


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_add_new_bond_iface_with_vxlan(eth1_up):
    eth_name = eth1_up[Interface.KEY][0][Interface.NAME]
    bond_name = "bond0"
    vxlan = VxlanState(id=VXLAN1_ID, base_if=bond_name, remote="192.168.100.2")
    with bond_interface(
        name=bond_name, port=[eth_name], extra_iface_state=None, create=False
    ) as bond_desired_state:
        with vxlan_interfaces(vxlan, create=False) as desired_state:
            desired_state[Interface.KEY].append(
                bond_desired_state[Interface.KEY][0]
            )
            libnmstate.apply(desired_state)
            assertlib.assert_state_match(desired_state)

    assertlib.assert_absent(vxlan.name)
    assertlib.assert_absent(bond_name)


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_show_vxlan_with_no_remote(eth1_up):
    eth_name = eth1_up[Interface.KEY][0][Interface.NAME]
    vxlan = VxlanState(id=VXLAN1_ID, base_if=eth_name, remote="")
    add_vxlan_cmd = (
        f"ip link add {vxlan.name} type vxlan id {vxlan.id}"
        f" dstport {vxlan.destination_port} dev {eth_name}".split()
    )
    try:
        ret = exec_cmd(add_vxlan_cmd)
        rc, _, _ = ret
        assert rc == RC_SUCCESS, format_exec_cmd_result(ret)
        desired_state = vxlans_down([vxlan])
        assertlib.assert_state(desired_state)
    finally:
        libnmstate.apply(vxlans_absent([vxlan]))
        assertlib.assert_absent(vxlan.name)


@pytest.mark.tier1
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_add_vxlan_and_modify_vxlan_id(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    ) as desired_state:
        assertlib.assert_state(desired_state)
        desired_state[Interface.KEY][0][VXLAN.CONFIG_SUBTREE][VXLAN.ID] = 200
        libnmstate.apply(desired_state)
        assertlib.assert_state(desired_state)

    vxlan1_ifname = desired_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)


@pytest.mark.tier1
@pytest.mark.skipif(
    nm_major_minor_version() < 1.31,
    reason="Modifying accept-all-mac-addresses is not supported on NM.",
)
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="https://issues.redhat.com/browse/RHEL-5001",
)
def test_vxlan_enable_and_disable_accept_all_mac_addresses(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    with vxlan_interfaces(
        VxlanState(id=VXLAN1_ID, base_if=ifname, remote="192.168.100.1")
    ) as d_state:
        d_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = True
        libnmstate.apply(d_state)
        assertlib.assert_state(d_state)

        d_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = False
        libnmstate.apply(d_state)
        assertlib.assert_state(d_state)

    vxlan1_ifname = d_state[Interface.KEY][0][Interface.NAME]
    assertlib.assert_absent(vxlan1_ifname)
