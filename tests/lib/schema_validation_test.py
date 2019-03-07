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
from __future__ import absolute_import

import copy

import pytest

import jsonschema as js

import libnmstate
from libnmstate.schema import Constants


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
            }
        }
    ],
    ROUTES: [
        {
            'table-name': 'main',
            'table-id': 254,
            'origin': 'static',
            'metric': 100,
            'destination': '0.0.0.0/0',
            'next-hop-interface': 'eth0',
            'next-hop-address': '192.0.2.1'
        },
        {
            'table-name': 'main',
            'table-id': 254,
            'origin': 'static',
            'metric': 100,
            'destination': '::/0',
            'next-hop-interface': 'eth0',
            'next-hop-address': 'fe80::1'
        },
    ]
}


@pytest.fixture
def default_data():
    return copy.deepcopy(COMMON_DATA)


class TestIfaceCommon(object):

    def test_valid_instance(self, default_data):
        libnmstate.validator.verify(default_data)

    def test_invalid_instance(self, default_data):
        default_data[INTERFACES][0]['state'] = 'bad-state'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.verify(default_data)
        assert 'bad-state' in err.value.args[0]

    def test_invalid_type(self, default_data):
        default_data[INTERFACES][0]['type'] = 'bad-type'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.verify(default_data)
        assert 'bad-type' in err.value.args[0]


class TestIfaceTypeEthernet(object):

    def test_valid_ethernet_with_auto_neg(self, default_data):
        default_data[INTERFACES][0].update({
            'type': 'ethernet',
            'auto-negotiation': True,
        })
        libnmstate.validator.verify(default_data)

    def test_valid_ethernet_without_auto_neg(self, default_data):
        default_data[INTERFACES][0].update({
            'auto-negotiation': False,
            'link-speed': 1000,
            'duplex': 'full',
        })
        libnmstate.validator.verify(default_data)

    def test_valid_without_auto_neg_and_missing_speed(self, default_data):
        """
        Defining autonegotiation as false and not specifying the link-speed is
        not a valid configuration, however, this is not handled by the schema
        at the moment, deferring the handling to the application code.
        """
        default_data[INTERFACES][0].update({
            'type': 'ethernet',
            'auto-negotiation': False,
        })
        del default_data[INTERFACES][0]['link-speed']

        libnmstate.validator.verify(default_data)


class TestRoutes(object):
    def test_valid_state_absent(self, default_data):
        default_data[ROUTES][0]['state'] = 'absent'
        libnmstate.validator.verify(default_data)

    def test_invalid_state(self, default_data):
        default_data[ROUTES][0]['state'] = 'bad-state'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.verify(default_data)
        assert 'bad-state' in err.value.args[0]

    def test_valid_origin_dhcp(self, default_data):
        default_data[ROUTES][0]['origin'] = 'dhcp'
        libnmstate.validator.verify(default_data)

    def test_valid_origin_ipv6_ra(self, default_data):
        default_data[ROUTES][0]['origin'] = 'router-advertisement'
        libnmstate.validator.verify(default_data)

    def test_invalid_origin(self, default_data):
        default_data[ROUTES][0]['origin'] = 'bad-origin'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.verify(default_data)
        assert 'bad-origin' in err.value.args[0]
