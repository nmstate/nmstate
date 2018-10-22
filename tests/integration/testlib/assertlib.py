#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import collections
import copy
import six

from . import statelib
from .statelib import INTERFACES


def assert_state(desired_state):
    """Given a state, assert it against the current state."""

    filtered_current_state = statelib.filter_current_state(desired_state)
    normalized_desired_state = _normalize_desired_state(desired_state,
                                                        filtered_current_state)

    assert normalized_desired_state == filtered_current_state


def _normalize_desired_state(desired_state, current_state):
    """
    Given the desired and current state, complement the desired state with all
    missing properties such that it will be a "full" state description.
    Note: It is common for the desired state to include only partial config,
    expecting nmstate to complement the missing parts from the current state.
    """
    desired_state = copy.deepcopy(desired_state)
    desired_interfaces_state = desired_state[INTERFACES]

    for current_iface_state in current_state[INTERFACES]:
        ifname = current_iface_state['name']
        desired_iface_state = _lookup_iface_state_by_name(
            desired_interfaces_state, ifname)
        if desired_iface_state is not None:
            normalized_desired_iface_state = _dict_update(
                copy.deepcopy(current_iface_state), desired_iface_state)
            desired_iface_state.update(normalized_desired_iface_state)
    return desired_state


def _lookup_iface_state_by_name(interfaces_state, ifname):
    for iface_state in interfaces_state:
        if iface_state['name'] == ifname:
            return iface_state
    return None


def _dict_update(origin_data, to_merge_data):
    """
    Recursively performs a dict update (merge), taking the to_merge_data and
    updating the origin_data.
    The function changes the origin_data in-place.
    """
    for key, val in six.viewitems(to_merge_data):
        if isinstance(val, collections.Mapping):
            origin_data[key] = _dict_update(origin_data.get(key, {}), val)
        else:
            origin_data[key] = val

    return origin_data
