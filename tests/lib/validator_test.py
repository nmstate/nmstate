#
# Copyright (c) 2021 Red Hat, Inc.
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

from libnmstate.error import NmstateValueError
from libnmstate.validator import validate_boolean
from libnmstate.validator import validate_integer
from libnmstate.validator import validate_list
from libnmstate.validator import validate_string


FOO_PROPERTY = "foo"


def test_validate_wrong_boolean():
    with pytest.raises(NmstateValueError):
        validate_boolean("notabool", FOO_PROPERTY)


def test_validate_boolean():
    validate_boolean(True, FOO_PROPERTY)


def test_validate_bigger_integer():
    with pytest.raises(NmstateValueError):
        validate_integer(100, FOO_PROPERTY, maximum=50)


def test_validate_lower_integer():
    with pytest.raises(NmstateValueError):
        validate_integer(0, FOO_PROPERTY, minimum=50)


def test_validate_wrong_integer():
    with pytest.raises(NmstateValueError):
        validate_integer("notint", FOO_PROPERTY)


def test_validate_integer():
    validate_integer(100, FOO_PROPERTY)


def test_validate_wrong_list():
    with pytest.raises(NmstateValueError):
        validate_list("notalist", FOO_PROPERTY)


def test_validate_mixed_list():
    with pytest.raises(NmstateValueError):
        validate_list([2, "a", True], FOO_PROPERTY, elem_type=str)


def test_validate_list():
    validate_list([1, 2, 3], FOO_PROPERTY, elem_type=int)


def test_validate_string():
    validate_string("simplestring", FOO_PROPERTY)


def test_validate_wrong_string():
    with pytest.raises(NmstateValueError):
        validate_string(True, FOO_PROPERTY)


def test_validate_not_valid_string():
    with pytest.raises(NmstateValueError):
        validate_string("notvalid", FOO_PROPERTY, ["valid"])
