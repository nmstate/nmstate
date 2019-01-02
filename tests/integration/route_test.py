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

import pytest

from libnmstate import netapplier
from libnmstate import validator

from .testlib import assertlib
from .testlib.statelib import INTERFACES, ROUTING


IPV4_ADDRESS1 = '192.0.2.251'
IPV4_ADDRESS2 = '192.0.2.252'
IPV4_BLOCK1 = '198.51.100.0/24'
IPV4_BLOCK2 = '203.0.113.0/24'
IPV6_ADDRESS1 = '2001:db8:1::1'
IPV6_ADDRESS3 = '2001:db8:1::2'
IPV6_BLOCK1 = '2001:db8:b1::/64'
IPV6_BLOCK2 = '2001:db8:b2::/64'


@pytest.mark.xfail(raises=validator.StaticRouteOnAutoIPNotSupportedError)
def test_ip4_static_route_on_auto_ip(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                }
            ],
            'ipv6': []
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'dhcp': True,
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.AutoRouteOnStaticIPNotSupportedError)
def test_ip4_auto_route_on_static_ip(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'auto',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'dhcp': False,
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.StaticRouteOnAutoIPNotSupportedError)
def test_ip6_static_route_on_auto_ip(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv6': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    'enabled': True,
                    'dhcp': True,
                    'autoconf': True
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.AutoRouteOnStaticIPNotSupportedError)
def test_ip6_auto_route_on_static_ip(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv6': [
                {
                    'route-type': 'auto',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    'enabled': True,
                    'dhcp': False,
                    'autoconf': False,
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.CannotSetOfflineRouteError)
def test_static_route_on_disabled_ip4(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': False,
                    'dhcp': False,
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.CannotSetOfflineRouteError)
def test_static_route_on_disabled_ip6(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv6': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    'enabled': False,
                    'dhcp': False,
                    'autoconf': False,
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.CannotSetOfflineRouteError)
def test_static_ipv4_route_on_disabled_nic(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'down',
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.CannotSetOfflineRouteError)
def test_static_ipv6_route_on_disabled_nic(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv6': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'down',
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.MultipleRouteTablesNotSupportedError)
def test_2_ipv6_route_table_per_nic(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv6': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': IPV6_BLOCK1,
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    'enabled': True,
                    'address': [
                        {'ip': IPV6_ADDRESS1, 'prefix-length': 64}
                    ]
                }
            }
        ]
    }
    netapplier.apply(desired_state)


@pytest.mark.xfail(raises=validator.MultipleRouteTablesNotSupportedError)
def test_2_ipv4_route_table_per_nic(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': IPV4_BLOCK1,
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                }
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'address': [
                        {'ip': IPV4_ADDRESS1, 'prefix-length': 24}
                    ]
                }
            }
        ]
    }
    netapplier.apply(desired_state)


def test_ipv4_static_route(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': IPV4_BLOCK1,
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': IPV4_BLOCK2,
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
            ],
            'ipv6': [],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'address': [
                        {'ip': IPV4_ADDRESS1, 'prefix-length': 24}
                    ]
                }
            }
        ]
    }
    netapplier.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv6_static_route(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [],
            'ipv6': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': IPV6_BLOCK1,
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 'main',
                    'destination': IPV6_BLOCK2,
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
            ],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    'enabled': True,
                    'address': [
                        {'ip': IPV6_ADDRESS1, 'prefix-length': 64}
                    ]
                }
            }
        ]
    }
    netapplier.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv4_static_route_interger_route_table(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv4': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': '0.0.0.0/0',
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': IPV4_BLOCK1,
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': IPV4_BLOCK2,
                    'next-hop': IPV4_ADDRESS2,
                    'metric': 100
                },
            ],
            'ipv6': [],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    'enabled': True,
                    'address': [
                        {'ip': IPV4_ADDRESS1, 'prefix-length': 24}
                    ]
                }
            }
        ]
    }
    netapplier.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_ipv6_static_route_interger_route_table(eth1_up):
    desired_state = {
        ROUTING: {
            'ipv6': [
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': '::/0',
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': IPV6_BLOCK1,
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
                {
                    'route-type': 'static',
                    'iface': 'eth1',
                    'route-table': 99,
                    'destination': IPV6_BLOCK2,
                    'next-hop': IPV6_ADDRESS3,
                    'metric': 100
                },
            ],
            'ipv4': [],
        },
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    'enabled': True,
                    'address': [
                        {'ip': IPV6_ADDRESS1, 'prefix-length': 64}
                    ]
                }
            }
        ]
    }
    netapplier.apply(desired_state)
    assertlib.assert_state(desired_state)
