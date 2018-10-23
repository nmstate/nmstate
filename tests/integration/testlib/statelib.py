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
from libnmstate.schema import Constants


INTERFACES = Constants.INTERFACES


def show_only(ifnames):
    """
    Report the current state, filtering based on the given interface names.
    """
    base_filter_state = {
        INTERFACES: [{'name': ifname} for ifname in ifnames]
    }
    return filter_current_state(base_filter_state)


def filter_current_state(desired_state):
    """
    Given the desired state, return a filtered version of the current state
    which includes only entities such as interfaces that have been mentioned
    in the desired state.
    In case there are no entities for filtering, all are reported.
    """
    current_state = netinfo.show()
    desired_iface_names = {ifstate['name']
                           for ifstate in desired_state[INTERFACES]}

    if not desired_iface_names:
        return current_state

    filtered_iface_current_state = [
        ifstate
        for ifstate in current_state[INTERFACES]
        if ifstate['name'] in desired_iface_names
    ]
    return {INTERFACES: filtered_iface_current_state}
