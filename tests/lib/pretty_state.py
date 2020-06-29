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

from libnmstate.prettystate import PrettyState

TEST_STATE = {
    "0": "a",
    "type": "unknown",
    "name": "foo",
    "ipv4": {"abc": 1, "enabled": "false"},
    "slaves": [{"a": 1, "name": "bar1"}, {"a": 2, "name": "bar2"}],
    "state": "up",
}

TEST_YAML_STATE = """---
name: foo
type: unknown
state: up
'0': a
ipv4:
  enabled: 'false'
  abc: 1
slaves:
- name: bar1
  a: 1
- name: bar2
  a: 2
"""

TEST_JSON_STATE = """{
    "name": "foo",
    "type": "unknown",
    "state": "up",
    "0": "a",
    "ipv4": {
        "enabled": "false",
        "abc": 1
    },
    "slaves": [
        {
            "name": "bar1",
            "a": 1
        },
        {
            "name": "bar2",
            "a": 2
        }
    ]
}"""


def test_pretty_state_order_with_priority():
    state = PrettyState(TEST_STATE)
    assert state.yaml == TEST_YAML_STATE


def test_json_ovs_bond_name_list_first():
    state = PrettyState(TEST_STATE)
    assert state.json == TEST_JSON_STATE
