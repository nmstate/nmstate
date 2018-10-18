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


import pytest

from libnmstate import netapplier

@pytest.fixture
def eth_state():
    return {
        'interfaces': [
            {'eth0':{
                'name': 'eth0',
                'enabled': True,
                'type': ' ethernetCsmacd',
                'mtu': 9000,
                }

            }
        ]
    }

def test_edit_nic_mtu(eth_state):
    eth_state['interfaces'][0]['mtu'][9000] = True
    eth_state['interfaces'][0]['mtu']['value'] =[
        {'mtu': 1500}]
    netapplier.apply(eth_state)