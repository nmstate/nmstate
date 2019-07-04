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

import libnmstate.nm.dns as nm_dns
import libnmstate.nm.nmclient as nmclient
import libnmstate.nm.ipv4 as nm_ipv4
import libnmstate.nm.ipv6 as nm_ipv6
from libnmstate.schema import DNS


class DnsState(object):
    def __init__(self, dict_state=None):
        if dict_state is None:
            dict_state = DnsState._get()

        self._config = dict_state.get(DNS.CONFIG, {})
        self._running = dict_state.get(DNS.RUNNING, {})

    @staticmethod
    def _get():
        client = nmclient.client()
        return {
            DNS.RUNNING: nm_dns.get_running(),
            DNS.CONFIG: nm_dns.get_config(
                nm_ipv4.acs_and_ip_profiles(client),
                nm_ipv6.acs_and_ip_profiles(client),
            ),
        }

    def dump(self):
        return {DNS.RUNNING: self._running, DNS.CONFIG: self._config}

    def merge_config(self, current):
        pass

    def generate_metadata(self, iface_state):
        pass

    def verify(self, current):
        pass

    def pre_merge_validate(self):
        pass

    def post_merge_validate(self):
        pass
