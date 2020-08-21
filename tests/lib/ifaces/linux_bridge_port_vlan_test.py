#
# Copyright (c) 2020 Red Hat, Inc.
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

from libnmstate.ifaces.linux_bridge_port_vlan import NmstateLinuxBridgePortVlan
from libnmstate.schema import LinuxBridge as LB


@pytest.mark.parametrize(
    "is_native_vlan", [True, False], ids=["native", "not-native"]
)
def test_bridge_vlan_trunk_port(is_native_vlan):
    info = {
        LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
        LB.Port.Vlan.TRUNK_TAGS: [
            {LB.Port.Vlan.TrunkTags.ID: 100},
            {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: 200,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: 300,
                }
            },
            {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: 300,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: 400,
                }
            },
        ],
        LB.Port.Vlan.ENABLE_NATIVE: is_native_vlan,
    }
    if is_native_vlan:
        info[LB.Port.Vlan.TAG] = 10
    nmstate_port = NmstateLinuxBridgePortVlan(info)

    kernel_vlans = nmstate_port.to_kernel_vlans()
    new_nmstate_port = NmstateLinuxBridgePortVlan.new_from_kernel_vlans(
        kernel_vlans
    )

    assert nmstate_port.to_dict() == new_nmstate_port.to_dict()


def test_bridge_vlan_access_port():
    info = {LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.ACCESS, LB.Port.Vlan.TAG: 100}
    nmstate_port = NmstateLinuxBridgePortVlan(info)

    kernel_vlans = nmstate_port.to_kernel_vlans()
    new_nmstate_port = NmstateLinuxBridgePortVlan.new_from_kernel_vlans(
        kernel_vlans
    )

    assert nmstate_port.to_dict() == new_nmstate_port.to_dict()


def test_bridge_vlan_trunk_port_range_to_flat():
    info = {
        LB.Port.Vlan.ENABLE_NATIVE: False,
        LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
        LB.Port.Vlan.TRUNK_TAGS: [
            {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: 101,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: 102,
                }
            },
            {
                LB.Port.Vlan.TrunkTags.ID_RANGE: {
                    LB.Port.Vlan.TrunkTags.MIN_RANGE: 103,
                    LB.Port.Vlan.TrunkTags.MAX_RANGE: 103,
                }
            },
        ],
    }
    nmstate_port = NmstateLinuxBridgePortVlan(info)
    expected_info = {
        LB.Port.Vlan.ENABLE_NATIVE: False,
        LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
        LB.Port.Vlan.TRUNK_TAGS: [
            {LB.Port.Vlan.TrunkTags.ID: 101},
            {LB.Port.Vlan.TrunkTags.ID: 102},
            {LB.Port.Vlan.TrunkTags.ID: 103},
        ],
    }
    assert nmstate_port.to_dict(expand_vlan_range=True) == expected_info
