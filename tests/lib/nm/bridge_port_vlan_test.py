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
from libnmstate.nm.bridge_port_vlan import PortVlanFilter
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
    port_vlan_filter = PortVlanFilter()
    port_vlan_filter.create_configuration(
        trunk_tags, ACCESS_TAG if is_native_vlan else None, is_native_vlan
    )
    nm_port_bridge_vlans = port_vlan_filter.to_nm()
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


@pytest.mark.parametrize(
    "trunk_tags",
    [
        [],
        [(100, 100)],
        [(100, 100), (200, 200)],
        [(100, 200)],
        [(100, 100), (200, 300)],
        [(100, 200), (300, 400)],
    ],
    ids=[
        "access-port",
        "single-trunk-tag",
        "two-trunk-tags",
        "one-tag-range",
        "mixed-tag-and-range",
        "multiple-ranges",
    ],
)
@pytest.mark.parametrize(
    "is_native_vlan", [False, True], ids=["not-native-vlan", "native-vlan"]
)
def test_bridge_port_vlan_to_dict(NM_mock, trunk_tags, is_native_vlan):
    port_vlans = _generate_port_vlan_mocks(
        trunk_tags, is_native_vlan, ACCESS_TAG
    )

    vlan_config = PortVlanFilter()
    vlan_config.import_from_bridge_settings(port_vlans)
    assert vlan_config.tag == (
        ACCESS_TAG if (not trunk_tags or is_native_vlan) else None
    )
    assert len(vlan_config.trunk_tags) == len(trunk_tags)
    assert vlan_config.is_native == (is_native_vlan and len(trunk_tags) > 0)
    assert vlan_config.to_dict() == _get_vlan_config_dict(
        trunk_tags, ACCESS_TAG, is_native_vlan
    )


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


def _assert_port_settings_vlan_conf(port_vlans, desired_vlans):
    expected_vlans = set(desired_vlans)
    for port_vlan in port_vlans:
        min_vlan, max_vlan = PortVlanFilter.get_vlan_tag_range(port_vlan)
        for i in range(min_vlan, max_vlan + 1):
            expected_vlans.remove(i)
    assert not expected_vlans, "vlans: {} were not configured".format(
        expected_vlans
    )


def _generate_port_vlan_mocks(trunk_tags, is_native_vlan, access_tag):
    port_vlans = []
    for trunk_tag in trunk_tags:
        min_tag_range, max_tag_range = (trunk_tag[i] for i in range(2))
        trunk_tag_vlan_config = _generate_bridge_vlan_mock(
            min_tag_range, max_tag_range, pvid=False, untagged=False
        )
        port_vlans.append(trunk_tag_vlan_config)
    if is_native_vlan or not trunk_tags:
        port_vlans.append(
            _generate_bridge_vlan_mock(
                access_tag, access_tag, pvid=True, untagged=True
            )
        )
    return port_vlans


def _generate_bridge_vlan_mock(
    min_tag_range, max_tag_range, pvid=False, untagged=False
):
    bridge_vlan = mock.MagicMock()
    bridge_vlan.is_untagged.return_value = untagged
    bridge_vlan.is_pvid.return_value = pvid
    bridge_vlan.to_str.return_value = "{}{}".format(
        min_tag_range,
        "-{}".format(max_tag_range) if max_tag_range != min_tag_range else "",
    )
    return bridge_vlan


def _get_vlan_config_dict(trunk_tags, access_tag, enable_native_vlan):
    vlan_config_dict = {
        LB.Port.Vlan.MODE: _get_port_vlan_mode(trunk_tags),
        LB.Port.Vlan.TRUNK_TAGS: _tag_list_to_trunk_tags(trunk_tags),
    }
    if trunk_tags:
        if enable_native_vlan:
            vlan_config_dict[LB.Port.Vlan.TAG] = access_tag
        vlan_config_dict[LB.Port.Vlan.ENABLE_NATIVE] = enable_native_vlan
    else:
        vlan_config_dict[LB.Port.Vlan.TAG] = access_tag
    return vlan_config_dict


def _tag_list_to_trunk_tags(tag_config_list):
    trunk_tags = []
    for tag_config in tag_config_list:
        min_range, max_range = tag_config
        if min_range == max_range:
            trunk_tags.append({LB.Port.Vlan.TrunkTags.ID: min_range})
        else:
            trunk_tags.append(
                {
                    LB.Port.Vlan.TrunkTags.ID_RANGE: {
                        LB.Port.Vlan.TrunkTags.MIN_RANGE: min_range,
                        LB.Port.Vlan.TrunkTags.MAX_RANGE: max_range,
                    }
                }
            )
    return trunk_tags


def _get_port_vlan_mode(trunk_tags):
    if not trunk_tags:
        return LB.Port.Vlan.Mode.ACCESS
    else:
        return LB.Port.Vlan.Mode.TRUNK
