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
from copy import deepcopy

from libnmstate.state import merge_dict


class TestMergeDict:
    def test_merge_empty(self):
        dict_to = {}
        dict_from = {}
        merge_dict(dict_to, dict_from)

        assert dict_to == {}
        assert dict_from == {}

    def test_merge_simple_dict(self):
        dict_to = {"a": 1}
        dict_from = {"a": 0, "b": "b"}
        merge_dict(dict_to, dict_from)

        assert dict_to == {"a": 1, "b": "b"}

    def test_merge_dict_with_list_value(self):
        dict_to = {"a": [1, 2, 3], "b": []}
        dict_from = {"a": [1, 3], "b": [3], "c": 5}

        merge_dict(dict_to, dict_from)

        assert dict_to == {"a": [1, 2, 3], "b": [], "c": 5}

    def test_merge_nested_dict(self):
        dict_to = {
            "a": {
                "a.1": {
                    "a.1.1": 1,
                    "a.1.2": "2",
                    "a.1.3": [3, 4, 5, 6, 7, 8, 9],
                }
            }
        }
        dict_from = {
            "a": {
                "a.1": {"a.1.3": [3], "a.1.4": [4, 5], "a.1.5": {}},
                "a.2": [1, 2, 3],
            },
            "b": 2,
        }

        merge_dict(dict_to, dict_from)

        assert dict_to == {
            "a": {
                "a.1": {
                    "a.1.1": 1,
                    "a.1.2": "2",
                    "a.1.3": [3, 4, 5, 6, 7, 8, 9],
                    "a.1.4": [4, 5],
                    "a.1.5": {},
                },
                "a.2": [1, 2, 3],
            },
            "b": 2,
        }

    def test_merge_with_from_unchanged(self):
        dict_to = {"a": 1, "b": "1"}
        dict_from = {"a": 2, "b": "2", "c": 3}
        expected_from = deepcopy(dict_from)

        merge_dict(dict_to, dict_from)

        assert dict_from == expected_from
        assert dict_to == {"a": 1, "b": "1", "c": 3}

    def test_merge_with_to_dict_contains_none_as_value(self):
        dict_to = {"a": 1, "b": None}
        dict_from = {"a": 2, "b": "2", "c": 3}
        expected_from = deepcopy(dict_from)

        merge_dict(dict_to, dict_from)

        assert dict_from == expected_from
        assert dict_to == {"a": 1, "b": None, "c": 3}

    def test_merge_with_from_dict_contains_none_as_value(self):
        dict_to = {"a": 1, "b": 3}
        dict_from = {"a": 2, "b": None, "c": None}
        expected_from = deepcopy(dict_from)

        merge_dict(dict_to, dict_from)

        assert dict_from == expected_from
        assert dict_to == {"a": 1, "b": 3, "c": None}
