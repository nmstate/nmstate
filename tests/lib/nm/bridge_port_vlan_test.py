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

from unittest import mock

from libnmstate import nm
from libnmstate.nm.bridge_port_vlan import nmstate_port_vlan_to_nm
from libnmstate.schema import LinuxBridge as LB


ACCESS_TAG = 4000


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.bridge_port_vlan, "NM") as m:
        yield m


def _get_port_vlan_ranged_trunks(min_vlan, max_vlan):
    return {
        LB.Port.Vlan.TrunkTags.ID_RANGE: {
            LB.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan,
            LB.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan,
        }
    }


def _port_vlan_trunk_tags_to_tag_list(trunk_tags, access_tag, enable_vlan):
    tag_list = []
    for trunk_tag in trunk_tags:
        single_tag = trunk_tag.get(LB.Port.Vlan.TrunkTags.ID)
        range_tags = trunk_tag.get(LB.Port.Vlan.TrunkTags.ID_RANGE, {})
        if single_tag:
            tag_list.append(single_tag)
        else:
            tag_list += range(
                range_tags.get(LB.Port.Vlan.TrunkTags.MIN_RANGE),
                range_tags.get(LB.Port.Vlan.TrunkTags.MAX_RANGE) + 1,
            )
    if enable_vlan:
        tag_list.append(access_tag)
    return tag_list


@pytest.mark.parametrize(
    "trunk_tags",
    [
        [],
        [{LB.Port.Vlan.TrunkTags.ID: 100}],
        [{LB.Port.Vlan.TrunkTags.ID: 100}, {LB.Port.Vlan.TrunkTags.ID: 101}],
        [_get_port_vlan_ranged_trunks(100, 199)],
        [
            _get_port_vlan_ranged_trunks(100, 199),
            _get_port_vlan_ranged_trunks(500, 1000),
        ],
        [
            {LB.Port.Vlan.TrunkTags.ID: 100},
            _get_port_vlan_ranged_trunks(500, 1000),
        ],
    ],
    ids=[
        "no-trunk-tags",
        "single-trunk-tag",
        "two-single-trunk-tags",
        "tag-ranges",
        "multiple-tag-ranges",
        "mixed-single-tag-and-tag-ranges",
    ],
)
@pytest.mark.parametrize(
    "is_native_vlan", [False, True], ids=["not-native-vlan", "native-vlan"]
)
def test_generate_nm_vlan_filtering_config(trunk_tags, is_native_vlan):
    vlan_config_info = {
        LB.Port.Vlan.ENABLE_NATIVE: is_native_vlan,
        LB.Port.Vlan.MODE: LB.Port.Vlan.Mode.TRUNK,
        LB.Port.Vlan.TRUNK_TAGS: trunk_tags,
    }

    if is_native_vlan:
        vlan_config_info[LB.Port.Vlan.TAG] = ACCESS_TAG

    nm_port_bridge_vlans = nmstate_port_vlan_to_nm(vlan_config_info)
    expected_trunk_tag_length = len(trunk_tags) + (1 if is_native_vlan else 0)
    assert expected_trunk_tag_length == len(nm_port_bridge_vlans)
    assert is_native_vlan == any(
        port_bridge_vlan.is_pvid() and port_bridge_vlan.is_untagged()
        for port_bridge_vlan in nm_port_bridge_vlans
    )
    desired_trunk_tags = _port_vlan_trunk_tags_to_tag_list(
        trunk_tags, ACCESS_TAG, is_native_vlan
    )
    _assert_port_settings_vlan_conf(nm_port_bridge_vlans, desired_trunk_tags)


def _assert_port_settings_vlan_conf(nm_port_vlans, desired_vlans):
    expected_vlans = set(desired_vlans)
    for nm_port_vlan in nm_port_vlans:
        _, min_vlan, max_vlan = nm_port_vlan.get_vid_range()
        for i in range(min_vlan, max_vlan + 1):
            expected_vlans.remove(i)
    assert not expected_vlans, "vlans: {} were not configured".format(
        expected_vlans
    )
