#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

import copy

import pytest

import jsonschema as js

import libnmstate


DEFAULT_DATA = {
    'interfaces': [
        {
            'name': 'lo',
            'description': 'Loopback Interface',
            'type': 'ethernet',
            'state': 'down',
            'link-speed': 1000,
            'mac-address': '12:34:56:78:90:ab',
            'mtu': 1500,
            # Read Only entries
            'if-index': 0,
            'admin-status': 'up',
            'link-status': 'down',
            'phys-address': '12:34:56:78:90:ab',
            'higher-layer-if': '',
            'lower-layer-if': '',
            'statistics': {
                'in-octets': 0,
                'in-unicast-pkts': 0,
                'in-broadcast-pkts': 0,
                'in-multicast-pkts': 0,
                'in-discards': 0,
                'in-errors': 0,
                'out-octets': 0,
                'out-unicast-pkts': 0,
                'out-broadcast-pkts': 0,
                'out-multicast-pkts': 0,
                'out-discards': 0,
                'out-errors': 0,
            }
        }
    ]
}


def test_valid_basic_instance():
    data = copy.deepcopy(DEFAULT_DATA)

    libnmstate.validator.verify(data)


def test_invalid_basic_instance():
    data = copy.deepcopy(DEFAULT_DATA)
    data['interfaces'][0]['state'] = 'bad-state'

    with pytest.raises(js.ValidationError) as err:
        libnmstate.validator.verify(data)
        assert 'bad-state' in err.value.args[0]
