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

import six


def get_slaves_from_state(state, default=()):
    ports = state.get('bridge', {}).get('port')
    if ports is None:
        return default
    return [p['name'] for p in ports]


def set_bridge_ports_metadata(master_state, slave_state):
    _set_common_slaves_metadata(master_state, slave_state)

    ports = master_state.get('bridge', {}).get('port', [])
    port = next(
        six.moves.filter(lambda n: n['name'] == slave_state['name'], ports),
        {}
    )
    slave_state['_brport_options'] = port


def _set_common_slaves_metadata(master_state, slave_state):
    slave_state['_master'] = master_state['name']
    slave_state['_master_type'] = master_state['type']
