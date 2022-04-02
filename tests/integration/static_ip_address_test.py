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
from libnmstate.iplib import is_ipv6_link_local_addr
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import statelib
from .testlib.dummy import nm_unmanaged_dummy
from .testlib.iproutelib import ip_monitor_assert_stable_link_up

# TEST-NET addresses: https://tools.ietf.org/html/rfc5737#section-3
IPV4_ADDRESS1 = "192.0.2.251"
IPV4_ADDRESS2 = "192.0.2.252"
IPV4_ADDRESS3 = "198.51.100.249"
IPV4_ADDRESS4 = "198.51.100.250"
# IPv6 Address Prefix Reserved for Documentation:
# https://tools.ietf.org/html/rfc3849
IPV6_ADDRESS1 = "2001:db8:1::1"
IPV6_ADDRESS2 = "2001:db8:2::1"
IPV6_LINK_LOCAL_ADDRESS1 = "fe80::1"
IPV6_LINK_LOCAL_ADDRESS2 = "fe80::2"

DUMMY1 = "dummy1"


@pytest.fixture
def setup_eth1_ipv4(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
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
    yield desired_state


@pytest.fixture
def setup_eth1_ipv6(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
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
def setup_eth1_static_ip(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Interface.IPV6: {
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
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    libnmstate.apply(desired_state)

    return desired_state


def test_add_static_ipv4_with_full_state(eth1_up):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]

    eth1_desired_state[Interface.STATE] = InterfaceState.UP
    eth1_desired_state[Interface.IPV4][InterfaceIPv4.ENABLED] = True
    eth1_desired_state[Interface.IPV4][InterfaceIPv4.ADDRESS] = [
        {
            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS3,
            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
        }
    ]
    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_add_static_ipv4_with_min_state(eth2_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth2",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
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


@pytest.mark.tier1
def test_remove_static_ipv4(setup_eth1_ipv4):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_edit_static_ipv4_address_and_prefix(setup_eth1_ipv4):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
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
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
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
                Interface.NAME: "eth2",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
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


@pytest.mark.tier1
def test_add_iface_with_same_static_ipv4_address_to_existing(
    setup_eth1_ipv4, eth2_up
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth2",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
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


@pytest.mark.tier1
def test_add_static_ipv6_with_full_state(eth1_up):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.STATE] = InterfaceState.UP
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ENABLED] = True
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS] = [
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
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.STATE] = InterfaceState.UP
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ENABLED] = True
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS] = [
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
    cur_state = statelib.show_only(("eth1",))
    eth1_cur_state = cur_state[Interface.KEY][0]
    assert (
        eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS][0]
        not in eth1_cur_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
    )
    assert (
        eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS][1]
        in eth1_cur_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
    )


def test_add_static_ipv6_with_link_local_only(eth1_up):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.STATE] = InterfaceState.UP
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ENABLED] = True
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS] = [
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
    cur_state = statelib.show_only(("eth1",))
    eth1_cur_state = cur_state[Interface.KEY][0]
    assert (
        eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS][0]
        not in eth1_cur_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
    )
    assert (
        eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS][1]
        not in eth1_cur_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
    )


@pytest.mark.tier1
def test_add_static_ipv6_with_no_address(eth1_up):
    desired_state = statelib.show_only(("eth1",))
    eth1_desired_state = desired_state[Interface.KEY][0]
    eth1_desired_state[Interface.STATE] = InterfaceState.UP
    eth1_desired_state[Interface.IPV6][InterfaceIPv6.ENABLED] = True

    libnmstate.apply(desired_state)

    cur_state = statelib.show_only(("eth1",))
    eth1_cur_state = cur_state[Interface.KEY][0]
    # Should have at least 1 link-local address.
    assert len(eth1_cur_state[Interface.IPV6][InterfaceIPv6.ADDRESS]) >= 1


def test_add_static_ipv6_with_min_state(eth2_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth2",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
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


@pytest.mark.tier1
def test_disable_static_ipv6(setup_eth1_ipv6):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }

    libnmstate.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.tier1
def test_disable_static_ipv6_and_rollback(setup_eth1_ipv6):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
                "foo": "bad_value",
            }
        ]
    }

    with pytest.raises(
        (
            libnmstate.error.NmstateVerificationError,
            libnmstate.error.NmstateValueError,
        )
    ):
        libnmstate.apply(desired_state)

    assertlib.assert_state(setup_eth1_ipv6)


@pytest.mark.tier1
def test_enable_ipv6_and_rollback_to_disable_ipv6(setup_eth1_ipv6_disable):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
                "foo": "bad_value",
            }
        ]
    }

    with pytest.raises(
        (
            libnmstate.error.NmstateVerificationError,
            libnmstate.error.NmstateValueError,
        )
    ):
        libnmstate.apply(desired_state)

    assertlib.assert_state(setup_eth1_ipv6_disable)


@pytest.mark.tier1
def test_edit_static_ipv6_address_and_prefix(setup_eth1_ipv6):
    eth1_setup = setup_eth1_ipv6[Interface.KEY][0]
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
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
    eth1_desired_state = desired_state[Interface.KEY][0]
    current_state = statelib.show_only(("eth1",))

    eth1_current_state = current_state[Interface.KEY][0]

    assert (
        eth1_desired_state[Interface.IPV6][InterfaceIPv6.ADDRESS][0]
        in eth1_current_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
    )

    assert (
        eth1_setup[Interface.IPV6][InterfaceIPv6.ADDRESS][0]
        not in eth1_current_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
    )


def test_add_ifaces_with_same_static_ipv6_address_in_one_transaction(
    eth1_up, eth2_up
):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
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
                Interface.NAME: "eth2",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
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
        Interface.KEY: [
            {
                Interface.NAME: "eth2",
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
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


def test_add_iface_with_static_ipv6_expanded_format(eth1_up):
    ipv6_addr_lead_zeroes = "2001:0db8:85a3:0000:0000:8a2e:0370:7331"
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: eth1_up[Interface.KEY][0][Interface.NAME],
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: ipv6_addr_lead_zeroes,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
        ]
    }
    libnmstate.apply(desired_state)
    assertlib.assert_state(desired_state)


@pytest.mark.tier1
@ip_monitor_assert_stable_link_up("eth1")
def test_modify_ipv4_with_reapply(setup_eth1_ipv4):
    ipv4_addr = IPV4_ADDRESS2
    ipv4_state = setup_eth1_ipv4[Interface.KEY][0][Interface.IPV4]
    ipv4_state[InterfaceIPv4.ADDRESS][0][InterfaceIPv4.ADDRESS_IP] = ipv4_addr
    libnmstate.apply(setup_eth1_ipv4)

    assertlib.assert_state(setup_eth1_ipv4)


@pytest.mark.tier1
@ip_monitor_assert_stable_link_up("eth1")
def test_modify_ipv6_with_reapply(setup_eth1_ipv6):
    ipv6_addr = IPV6_ADDRESS2
    ipv6_state = setup_eth1_ipv6[Interface.KEY][0][Interface.IPV6]
    ipv6_state[InterfaceIPv6.ADDRESS][0][InterfaceIPv6.ADDRESS_IP] = ipv6_addr
    libnmstate.apply(setup_eth1_ipv6)

    assertlib.assert_state(setup_eth1_ipv6)


@pytest.mark.tier1
def test_get_ip_address_from_unmanaged_dummy():
    with nm_unmanaged_dummy(DUMMY1):
        cmdlib.exec_cmd(
            f"ip addr add {IPV4_ADDRESS1}/24 dev {DUMMY1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"ip -6 addr add {IPV6_ADDRESS2}/64 dev {DUMMY1}".split(),
            check=True,
        )
        iface_state = statelib.show_only((DUMMY1,))[Interface.KEY][0]
        # Remove IPv6 link local address
        iface_state[Interface.IPV6][InterfaceIPv6.ADDRESS] = [
            addr
            for addr in iface_state[Interface.IPV6][InterfaceIPv6.ADDRESS]
            if not is_ipv6_link_local_addr(
                addr[InterfaceIPv6.ADDRESS_IP],
                addr[InterfaceIPv6.ADDRESS_PREFIX_LENGTH],
            )
        ]

        assert iface_state[Interface.IPV4] == {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: [
                {
                    InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }

        assert iface_state[Interface.IPV6] == {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: [
                {
                    InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS2,
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            ],
        }


def test_ignore_invalid_ip_on_absent_interface(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.STATE: InterfaceState.ABSENT,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: "a.a.a.a",
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: "::g",
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                    },
                }
            ]
        }
    )


@pytest.mark.tier1
def test_preserve_ip_conf_if_not_mentioned(setup_eth1_static_ip):
    desired_state = setup_eth1_static_ip
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                }
            ]
        }
    )
    assertlib.assert_state_match(desired_state)
