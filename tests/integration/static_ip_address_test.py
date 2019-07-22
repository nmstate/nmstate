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

import pytest

import libnmstate
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from .testlib import assertlib
from .testlib import statelib
from .testlib.statelib import INTERFACES

# TEST-NET addresses: https://tools.ietf.org/html/rfc5737#section-3
IPV4_ADDRESS1 = '192.0.2.251'
IPV4_ADDRESS2 = '192.0.2.252'
IPV4_ADDRESS3 = '198.51.100.249'
IPV4_ADDRESS4 = '198.51.100.250'
# IPv6 Address Prefix Reserved for Documentation:
# https://tools.ietf.org/html/rfc3849
IPV6_ADDRESS1 = '2001:db8:1::1'
IPV6_ADDRESS2 = '2001:db8:2::1'
IPV6_LINK_LOCAL_ADDRESS1 = 'fe80::1'
IPV6_LINK_LOCAL_ADDRESS2 = 'fe80::2'


@pytest.fixture
def setup_eth1_ipv4(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)


@pytest.fixture
def setup_eth1_ipv6(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    return desired_state


@pytest.fixture
def setup_eth1_ipv6_disable(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    libnmstate.apply(desired_state)

    return desired_state


def test_add_static_ipv4_with_full_state(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]

    eth1_desired_state['state'] = 'up'
    eth1_desired_state['ipv4'][InterfaceIPv4.ENABLED] = True
    eth1_desired_state['ipv4'][InterfaceIPv4.ADDRESS] = [
        {
            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS3,
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
        }
    ]
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_add_static_ipv4_with_min_state(eth2_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth2',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS4,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_remove_static_ipv4(setup_eth1_ipv4):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'ipv4': {InterfaceIPv4.ENABLED: False},
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_edit_static_ipv4_address_and_prefix(setup_eth1_ipv4):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS2,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 30,
                        }
                    ],
                },
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_add_ifaces_with_same_static_ipv4_address_in_one_transaction(
    eth1_up, eth2_up
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
            },
            {
                'name': 'eth2',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
            },
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_add_iface_with_same_static_ipv4_address_to_existing(
    setup_eth1_ipv4, eth2_up
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth2',
                'type': 'ethernet',
                'state': 'up',
                'ipv4': {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_add_static_ipv6_with_full_state(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS] = [
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        },
        # This sequence is intentionally made for IP address sorting.
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        },
    ]
    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)


def test_add_static_ipv6_with_link_local(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS] = [
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_LINK_LOCAL_ADDRESS1,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        },
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        },
    ]

    libnmstate.apply(desired_state)

    # Make sure only the link local address got ignored.
    cur_state = statelib.show_only(('eth1',))
    eth1_cur_state = cur_state[INTERFACES][0]
    assert (
        eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS][0]
        not in eth1_cur_state['ipv6'][InterfaceIPv6.ADDRESS]
    )
    assert (
        eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS][1]
        in eth1_cur_state['ipv6'][InterfaceIPv6.ADDRESS]
    )


def test_add_static_ipv6_with_link_local_only(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True
    eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS] = [
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_LINK_LOCAL_ADDRESS1,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        },
        {
            InterfaceIPv6.ADDRESS_IP: IPV6_LINK_LOCAL_ADDRESS2,
            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
        },
    ]

    libnmstate.apply(desired_state)

    # Make sure the link local address got ignored.
    cur_state = statelib.show_only(('eth1',))
    eth1_cur_state = cur_state[INTERFACES][0]
    assert (
        eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS][0]
        not in eth1_cur_state['ipv6'][InterfaceIPv6.ADDRESS]
    )
    assert (
        eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS][1]
        not in eth1_cur_state['ipv6'][InterfaceIPv6.ADDRESS]
    )


def test_add_static_ipv6_with_no_address(eth1_up):
    desired_state = statelib.show_only(('eth1',))
    eth1_desired_state = desired_state[INTERFACES][0]
    eth1_desired_state['state'] = 'up'
    eth1_desired_state['ipv6'][InterfaceIPv6.ENABLED] = True

    libnmstate.apply(desired_state)

    cur_state = statelib.show_only(('eth1',))
    eth1_cur_state = cur_state[INTERFACES][0]
    # Should have at least 1 link-local address.
    assert len(eth1_cur_state['ipv6'][InterfaceIPv6.ADDRESS]) >= 1


def test_add_static_ipv6_with_min_state(eth2_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth2',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_disable_static_ipv6(setup_eth1_ipv6):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'ipv6': {InterfaceIPv6.ENABLED: False},
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.xfail(
    reason='https://nmstate.atlassian.net/browse/NMSTATE-231',
    raises=AssertionError,
    strict=True,
)
def test_disable_static_ipv6_and_rollback(setup_eth1_ipv6):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'ipv6': {InterfaceIPv6.ENABLED: False},
                'foo': 'bad_value',
            }
        ]
    }

    with pytest.raises(libnmstate.error.NmstateVerificationError):
        libnmstate.apply(desired_state)

    assertlib.assert_state(setup_eth1_ipv6)


def test_enable_ipv6_and_rollback_to_disable_ipv6(setup_eth1_ipv6_disable):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
                'foo': 'bad_value',
            }
        ]
    }

    with pytest.raises(libnmstate.error.NmstateVerificationError):
        libnmstate.apply(desired_state)

    assertlib.assert_state(setup_eth1_ipv6_disable)


def test_edit_static_ipv6_address_and_prefix(setup_eth1_ipv6):
    eth1_setup = setup_eth1_ipv6[INTERFACES][0]
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
        ]
    }

    libnmstate.apply(desired_state)
    eth1_desired_state = desired_state[INTERFACES][0]
    current_state = statelib.show_only(('eth1',))

    eth1_current_state = current_state[INTERFACES][0]

    assert (
        eth1_desired_state['ipv6'][InterfaceIPv6.ADDRESS][0]
        in eth1_current_state['ipv6'][InterfaceIPv6.ADDRESS]
    )

    assert (
        eth1_setup['ipv6'][InterfaceIPv6.ADDRESS][0]
        not in eth1_current_state['ipv6'][InterfaceIPv6.ADDRESS]
    )


def test_add_ifaces_with_same_static_ipv6_address_in_one_transaction(
    eth1_up, eth2_up
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            },
            {
                'name': 'eth2',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            },
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


def test_add_iface_with_same_static_ipv6_address_to_existing(
    setup_eth1_ipv6, eth2_up
):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth2',
                'type': 'ethernet',
                'state': 'up',
                'ipv6': {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)
