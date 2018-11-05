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

from libnmstate import netinfo

from . import statelib


def assert_state(desired_state_data):
    """Given a state, assert it against the current state."""

    current_state_data = netinfo.show()
    current_state = statelib.State(current_state_data)
    current_state.filter(desired_state_data)
    current_state.normalize()

    full_desired_state = statelib.State(current_state.state)
    full_desired_state.update(desired_state_data)
    full_desired_state.remove_absent_entries()
    full_desired_state.normalize()

    assert full_desired_state.state == current_state.state
