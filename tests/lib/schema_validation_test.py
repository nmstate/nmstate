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
from __future__ import absolute_import

import copy

import pytest

import jsonschema as js

import libnmstate
from libnmstate.schema import Constants
from libnmstate.schema import DNS


INTERFACES = Constants.INTERFACES
ROUTES = Constants.ROUTES


COMMON_DATA = {
    INTERFACES: [
        {
            'name': 'lo',
            'description': 'Loopback Interface',
            'type': 'unknown',
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
            'low-control': True,
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
            },
        },
        {
            'name': 'br0',
            'state': 'up',
            'type': 'linux-bridge',
            'bridge': {
                'options': {
                    'vlan-filtering': True,
                    'vlans': [
                        {'vlan-range-min': 10},
                        {'vlan-range-min': 100, 'vlan-range-max': 200},
                    ],
                },
                'ports': [],
            },
        },
    ],
    ROUTES: {
        'config': [
            {
                'table-id': 254,
                'metric': 100,
                'destination': '0.0.0.0/0',
                'next-hop-interface': 'eth0',
                'next-hop-address': '192.0.2.1',
            }
        ],
        'running': [
            {
                'table-id': 254,
                'metric': 100,
                'destination': '::/0',
                'next-hop-interface': 'eth0',
                'next-hop-address': 'fe80::1',
            }
        ],
    },
    DNS.KEY: {
        DNS.RUNNING: {
            DNS.SERVER: ["2001:db8::1", "192.0.2.1"],
            DNS.SEARCH: ["example.com", "example.org"],
        },
        DNS.CONFIG: {
            DNS.SERVER: ["2001:db8::1", "192.0.2.1"],
            DNS.SEARCH: ["example.com", "example.org"],
        },
    },
}


@pytest.fixture
def default_data():
    return copy.deepcopy(COMMON_DATA)


class TestIfaceCommon(object):
    def test_valid_instance(self, default_data):
        libnmstate.validator.validate(default_data)

    def test_invalid_instance(self, default_data):
        default_data[INTERFACES][0]['state'] = 'bad-state'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'bad-state' in err.value.args[0]

    def test_invalid_type(self, default_data):
        default_data[INTERFACES][0]['type'] = 'bad-type'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'bad-type' in err.value.args[0]


class TestIfaceTypeEthernet(object):
    def test_valid_ethernet_with_auto_neg(self, default_data):
        default_data[INTERFACES][0].update(
            {'type': 'ethernet', 'auto-negotiation': True}
        )
        libnmstate.validator.validate(default_data)

    def test_valid_ethernet_without_auto_neg(self, default_data):
        default_data[INTERFACES][0].update(
            {'auto-negotiation': False, 'link-speed': 1000, 'duplex': 'full'}
        )
        libnmstate.validator.validate(default_data)

    def test_valid_without_auto_neg_and_missing_speed(self, default_data):
        """
        Defining autonegotiation as false and not specifying the link-speed is
        not a valid configuration, however, this is not handled by the schema
        at the moment, deferring the handling to the application code.
        """
        default_data[INTERFACES][0].update(
            {'type': 'ethernet', 'auto-negotiation': False}
        )
        del default_data[INTERFACES][0]['link-speed']

        libnmstate.validator.validate(default_data)


class TestRoutes(object):
    def test_valid_state_absent(self, default_data):
        default_data[ROUTES]['config'][0]['state'] = 'absent'
        libnmstate.validator.validate(default_data)

    def test_invalid_state(self, default_data):
        default_data[ROUTES]['config'][0]['state'] = 'bad-state'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'bad-state' in err.value.args[0]


class TestVlanFiltering(object):
    def test_basic_configuration(self, default_data):
        libnmstate.validator.validate(default_data)

    def test_port_configuration(self, default_data):
        default_data[INTERFACES][1]['bridge']['ports'].append(
            {
                'name': 'eth1',
                'vlans': [{'vlan-range-min': 50, 'vlan-range-max': 80}],
            }
        )
        libnmstate.validator.validate(default_data)

    def test_invalid_linux_bridge_vlan_range(self, default_data):
        vlan_configs = default_data[INTERFACES][1]['bridge']['options'][
            'vlans'
        ]
        for vlan in vlan_configs:
            vlan['vlan-range-min'] = 'boom!'
        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'boom!' in err.value.args[0]

        for vlan in vlan_configs:
            vlan['vlan-range-min'] = 5000
        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert '5000 is greater than the maximum of 4095' in err.value.args[0]
