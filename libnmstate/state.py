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

from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from functools import total_ordering
import logging


PASSWORD_HID_BY_NMSTATE = "<_password_hid_by_nmstate>"


@total_ordering
class StateEntry(metaclass=ABCMeta):
    @abstractmethod
    def _keys(self):
        """
        Return the tuple representing this entry, will be used for hashing or
        comparing.
        """
        pass

    def __hash__(self):
        return hash(self._keys())

    def __eq__(self, other):
        return self is other or self._keys() == other._keys()

    def __lt__(self, other):
        return self._keys() < other._keys()

    def __repr__(self):
        return str(self.to_dict())

    @property
    @abstractmethod
    def absent(self):
        pass

    def to_dict(self):
        return {
            key.replace("_", "-"): value
            for key, value in vars(self).items()
            if (not key.startswith("_")) and (value is not None)
        }

    def match(self, other):
        """
        Match self against other. Treat self None attributes as wildcards,
        matching against any value in others.
        Return True for a match, False otherwise.
        """
        for self_value, other_value in zip(self._keys(), other._keys()):
            if self_value is not None and self_value != other_value:
                return False
        return True


def state_match(desire, current):
    """
    Return True when all values defined in desire equal to value in current,
    else False:
        * For mapping(e.g. dict), desire could have less value than current.
        * For sequnce(e.g. list), desire should equal to current.
    """
    if isinstance(desire, Mapping):
        return isinstance(current, Mapping) and all(
            state_match(val, current.get(key)) for key, val in desire.items()
        )
    elif isinstance(desire, Sequence) and not isinstance(desire, str):
        return (
            isinstance(current, Sequence)
            and not isinstance(current, str)
            and len(current) == len(desire)
            and all(state_match(d, c) for d, c in zip(desire, current))
        )
    else:
        return desire == current


def merge_dict(dict_to, dict_from):
    """
    Data will copy from `dict_from` if undefined in `dict_to`.
    For list, the whole list is copied instead of merging.
    """
    for key, from_value in dict_from.items():
        if key not in dict_to:
            dict_to[key] = from_value
        elif isinstance(dict_to[key], Mapping):
            merge_dict(dict_to[key], from_value)


def hide_the_secrets(state):
    if isinstance(state, Mapping):
        for key, value in state.items():
            if isinstance(value, Mapping) or isinstance(value, list):
                hide_the_secrets(value)
            elif key.endswith("password") and isinstance(value, str):
                state[key] = PASSWORD_HID_BY_NMSTATE
    elif isinstance(state, list):
        for value in state:
            hide_the_secrets(value)


def remove_the_reserved_secrets(state):
    if isinstance(state, Mapping):
        keys_to_remove = []
        for key, value in state.items():
            if isinstance(value, Mapping) or isinstance(value, list):
                remove_the_reserved_secrets(value)
            elif key.endswith("password") and value == PASSWORD_HID_BY_NMSTATE:
                logging.warn(
                    "Got nmstate reserved password"
                    f"({PASSWORD_HID_BY_NMSTATE}) for key: {key}, "
                    "will use current password if available."
                )
                keys_to_remove.append(key)
        for key in keys_to_remove:
            state.pop(key)

    elif isinstance(state, list):
        for value in state:
            remove_the_reserved_secrets(value)
