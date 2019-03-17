#
# Copyright 2019 Red Hat, Inc.
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

import copy
import six

from libnmstate.schema import Constants


INTERFACES = Constants.INTERFACES


class State(object):
    def __init__(self, state):
        self._state = copy.deepcopy(state)
        self._ifaces_state = self._index_interfaces_state_by_name()

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

    @property
    def interfaces(self):
        """ Indexed interfaces state """
        return self._ifaces_state

    def sanitize_ethernet(self, other_state):
        """
        Given the other_state, update the ethernet interfaces state base on
        the other_state ethernet interfaces data.
        Usually the other_state represents the current state.
        If auto-negotiation, speed and duplex settings are not provided,
        but exist in the current state, they need to be set to None
        to not override them with the values from the current settings
        since the current settings are read from the device state and not
        from the actual configuration.  This makes it possible to distinguish
        whether a user specified these values in the later configuration step.
        """
        for ifname, iface_state in six.viewitems(self.interfaces):
            iface_current_state = other_state.interfaces.get(ifname, {})
            if iface_current_state.get('type') == 'ethernet':
                ethernet = iface_state.setdefault('ethernet', {})
                ethernet.setdefault('auto-negotiation', None)
                ethernet.setdefault('speed', None)
                ethernet.setdefault('duplex', None)

    def sanitize_dynamic_ip(self):
        """
        If dynamic IP is enabled and IP address is missing, set an empty
        address list. This assures that the desired state is not complemented
        by the current state address values.
        If dynamic IP is disabled, all dynamic IP options should be removed.
        """
        for iface_state in six.viewvalues(self.interfaces):
            for family in ('ipv4', 'ipv6'):
                ip = iface_state.get(family, {})
                if ip.get('enabled') and (
                        ip.get('dhcp') or ip.get('autoconf')):
                    ip['address'] = []
                else:
                    for dhcp_option in ('auto-routes',
                                        'auto-gateway',
                                        'auto-dns'):
                        ip.pop(dhcp_option, None)

    def _index_interfaces_state_by_name(self):
        return {iface['name']: iface for iface in self._state[INTERFACES]}
