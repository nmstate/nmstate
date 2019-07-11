#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

try:
    from collections.abc import Mapping
    from collections.abc import Sequence
except ImportError:
    from collections import Mapping
    from collections import Sequence

import copy
from operator import itemgetter
import six

import libnmstate
from libnmstate.schema import Constants


INTERFACES = Constants.INTERFACES


def show_only(ifnames):
    """
    Report the current state, filtering based on the given interface names.
    """
    base_filter_state = {INTERFACES: [{'name': ifname} for ifname in ifnames]}
    current_state = State(libnmstate.show())
    current_state.filter(base_filter_state)
    return current_state.state


class State(object):
    def __init__(self, state):
        self._state = copy.deepcopy(state)

    def __eq__(self, other):
        return self._state == other

    def __hash__(self):
        return hash(self._state)

    def __str__(self):
        return self._state

    def __repr__(self):
        return self.__str__()

    @property
    def state(self):
        return self._state

    def filter(self, based_on_state):
        """
        Given the based_on_state, update the sate with a filtered version
        which includes only entities such as interfaces that have been
        mentioned in the based_on_state.
        In case there are no entities for filtering, all are reported.
        """
        base_iface_names = {
            ifstate['name'] for ifstate in based_on_state[INTERFACES]
        }

        if not base_iface_names:
            return

        filtered_iface_state = [
            ifstate
            for ifstate in self._state[INTERFACES]
            if ifstate['name'] in base_iface_names
        ]
        self._state = {INTERFACES: filtered_iface_state}

    def update(self, other_state):
        """
        Given the other_state, update the state with the other_state data.
        """
        other_state = copy.deepcopy(other_state)
        other_interfaces_state = other_state[INTERFACES]

        for base_iface_state in self._state[INTERFACES]:
            ifname = base_iface_state['name']
            other_iface_state = _lookup_iface_state_by_name(
                other_interfaces_state, ifname
            )
            if other_iface_state is not None:
                iface_state = _dict_update(base_iface_state, other_iface_state)
                other_iface_state.update(iface_state)

        self._state = other_state

    def normalize(self):
        self._sort_iface_lag_slaves()
        self._sort_iface_bridge_ports()
        self._ipv4_skeleton_canonicalization()
        self._ipv6_skeleton_canonicalization()
        self._ignore_dhcp_manual_addr()
        self._ignore_dhcp_option_when_off()
        self._ignore_ipv6_link_local()
        self._sort_ip_addresses()
        self._sort_interfaces_by_name()

    def match(self, other):
        return _state_match(self.state, other.state)

    def _sort_interfaces_by_name(self):
        self._state[INTERFACES].sort(key=lambda d: d['name'])

    def remove_absent_entries(self):
        self._state[INTERFACES] = [
            ifstate
            for ifstate in self._state[INTERFACES]
            if ifstate.get('state') != 'absent'
        ]

    def _sort_iface_lag_slaves(self):
        for ifstate in self._state[INTERFACES]:
            ifstate.get('link-aggregation', {}).get('slaves', []).sort()

    def _sort_iface_bridge_ports(self):
        for ifstate in self._state[INTERFACES]:
            ifstate.get('bridge', {}).get('port', []).sort(
                key=itemgetter('name')
            )

    def _ipv6_skeleton_canonicalization(self):
        for iface_state in self._state.get(INTERFACES, []):
            iface_state.setdefault('ipv6', {})
            iface_state['ipv6'].setdefault('enabled', False)
            iface_state['ipv6'].setdefault('address', [])
            iface_state['ipv6'].setdefault('dhcp', False)
            iface_state['ipv6'].setdefault('autoconf', False)

    def _ipv4_skeleton_canonicalization(self):
        for iface_state in self._state.get(INTERFACES, []):
            iface_state.setdefault('ipv4', {})
            iface_state['ipv4'].setdefault('enabled', False)
            iface_state['ipv4'].setdefault('address', [])
            iface_state['ipv4'].setdefault('dhcp', False)

    def _ignore_ipv6_link_local(self):
        for iface_state in self._state.get(INTERFACES, []):
            iface_state['ipv6']['address'] = list(
                addr
                for addr in iface_state['ipv6']['address']
                if not _is_ipv6_link_local(addr['ip'], addr['prefix-length'])
            )

    def _sort_ip_addresses(self):
        for iface_state in self._state.get(INTERFACES, []):
            for family in ('ipv4', 'ipv6'):
                iface_state.get(family, {}).get('address', []).sort(
                    key=itemgetter('ip')
                )

    def _ignore_dhcp_manual_addr(self):
        for iface_state in self._state.get(INTERFACES, []):
            for family in ('ipv4', 'ipv6'):
                if iface_state.get(family, {}).get('dhcp'):
                    iface_state[family]['address'] = []

    def _ignore_dhcp_option_when_off(self):
        for iface_state in self._state.get(INTERFACES, []):
            for family in ('ipv4', 'ipv6'):
                ip = iface_state.get(family, {})
                if not (
                    ip.get('enabled')
                    and (ip.get('dhcp') or ip.get('autoconf'))
                ):
                    for dhcp_option in (
                        'auto-routes',
                        'auto-gateway',
                        'auto-dns',
                    ):
                        ip.pop(dhcp_option, None)


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
        if isinstance(val, Mapping):
            origin_data[key] = _dict_update(origin_data.get(key, {}), val)
        else:
            origin_data[key] = val

    return origin_data


def filter_current_state(desired_state):
    """
    Given the desired state, return a filtered version of the current state
    which includes only entities such as interfaces that have been mentioned
    in the desired state.
    In case there are no entities for filtering, all are reported.
    """
    current_state = libnmstate.show()
    desired_iface_names = {
        ifstate['name'] for ifstate in desired_state[INTERFACES]
    }

    if not desired_iface_names:
        return current_state

    filtered_iface_current_state = [
        ifstate
        for ifstate in current_state[INTERFACES]
        if ifstate['name'] in desired_iface_names
    ]
    return {INTERFACES: filtered_iface_current_state}


def _is_ipv6_link_local(ip, prefix):
    """
    The IPv6 link local address range is fe80::/10.
    """
    return ip[:3] in ['fe8', 'fe9', 'fea', 'feb'] and prefix >= 10


def _state_match(desire, current):
    if isinstance(desire, Mapping):
        return isinstance(current, Mapping) and all(
            _state_match(val, current.get(key))
            for key, val in six.viewitems(desire)
        )
    elif isinstance(desire, Sequence) and not isinstance(
        desire, six.string_types
    ):
        return (
            isinstance(current, Sequence)
            and not isinstance(current, six.string_types)
            and len(current) == len(desire)
            and all(_state_match(d, c) for d, c in zip(desire, current))
        )
    else:
        return desire == current
