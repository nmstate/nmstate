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

from libnmstate.state import state_match


class TestStateMatch:
    def test_match_empty_dict(self):
        assert state_match({}, {})

    def test_match_empty_list(self):
        assert state_match([], [])

    def test_match_none(self):
        assert state_match(None, None)

    def test_match_dict_vs_list(self):
        assert not state_match({}, [])

    def test_match_list_vs_string(self):
        assert not state_match(["a", "b", "c"], "abc")

    def test_match_dict_identical(self):
        assert state_match({"a": 1, "b": 2}, {"a": 1, "b": 2})

    def test_match_dict_current_has_more_data(self):
        assert state_match({"a": 1}, {"a": 1, "b": 2})

    def test_match_dict_desire_has_more_data(self):
        assert not state_match({"a": 1, "b": 2}, {"a": 1})

    def test_match_dict_different_value_type(self):
        assert not state_match({"a": 1, "b": []}, {"a": 1, "b": 2})

    def test_match_list_identical(self):
        assert state_match(["a", "b", 1], ["a", "b", 1])

    def test_match_list_different_order(self):
        assert not state_match(["a", "b", 1], ["a", 1, "b"])

    def test_match_list_current_contains_more(self):
        assert not state_match(["a", "b", 1], ["a", "b", "c", 1])

    def test_match_indentical_set(self):
        assert state_match(set(["a", "b", 1]), set(["a", "b", 1]))
        assert state_match(set(["a", 1, "b"]), set(["a", "b", 1]))
        assert state_match(set(["a", 1, 1, "b"]), set(["a", "b", 1]))

    def test_match_parital_set(self):
        assert not state_match(set(["a", "b", 1]), set(["a", "b", "c", 1]))

    def test_match_nested_list_in_dict(self):
        assert state_match({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]})

    def test_match_nested_dict_in_list(self):
        assert state_match(
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
        )
        assert state_match(
            [{"a": 1}, {"a": 2, "b": [3, 4]}],
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
        )
        assert not state_match(
            [{"a": 2, "b": [3, 4]}, {"a": 1, "b": [1, 2]}],
            [{"a": 1, "b": [1, 2]}, {"a": 2, "b": [3, 4]}],
        )
