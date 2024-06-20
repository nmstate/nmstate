# SPDX-License-Identifier: LGPL-2.1-or-later

import copy

import pytest

import libnmstate
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route

from ..testlib import assertlib
from ..testlib import cmdlib


DUMMY0 = "dummy0"
ETH1 = "eth1"
TEST_DNS_SRVS = ["192.0.2.2", "192.0.2.1"]


@pytest.fixture
def unmanaged_eth1_with_static_gw(eth1_up):
    try:
        cmdlib.exec_cmd(f"nmcli connection delete {ETH1}".split(), check=False)
        cmdlib.exec_cmd(f"nmcli dev set {ETH1} managed no".split(), check=True)
        cmdlib.exec_cmd(
            f"ip addr add 192.0.2.2/24 dev {ETH1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"ip route add default via 192.0.2.1 dev {ETH1} proto "
            "static metric 101".split(),
            check=True,
        )
        cmdlib.exec_cmd(f"ip link set {ETH1} up".split(), check=True)
        yield
    finally:
        cmdlib.exec_cmd(
            f"ip route del default via 192.0.2.1 dev {ETH1}".split(),
            check=False,
        )

        cmdlib.exec_cmd(
            f"ip addr del 192.0.2.2/24 dev {ETH1}".split(), check=False
        )
        cmdlib.exec_cmd(
            f"nmcli dev set {ETH1} managed yes".split(), check=False
        )


def test_set_auto_dns_with_unamanged_iface_with_static_gw(
    unmanaged_eth1_with_static_gw,
):
    desired_state = {
        DNS.KEY: {DNS.CONFIG: {DNS.SERVER: ["1.1.1.1"]}},
        Interface.KEY: [
            {
                Interface.NAME: DUMMY0,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: True,
                    InterfaceIPv4.AUTO_DNS: False,
                    InterfaceIPv4.AUTO_ROUTES: True,
                    InterfaceIPv4.AUTO_GATEWAY: True,
                },
            }
        ],
    }
    libnmstate.apply(desired_state)
    try:
        assertlib.assert_state(desired_state)
    finally:
        absent_state = {
            DNS.KEY: {DNS.CONFIG: {DNS.SERVER: []}},
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY0,
                    Interface.TYPE: InterfaceType.DUMMY,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ],
        }
        libnmstate.apply(absent_state)


@pytest.fixture
def all_unmanaged_with_gw_on_eth1(unmanaged_eth1_with_static_gw):
    changed_ifaces = []
    output = cmdlib.exec_cmd("nmcli -t -f DEVICE,STATE d".split(), check=True)[
        1
    ]
    for line in output.split("\n"):
        splited = line.split(":")
        if len(splited) == 2:
            iface_name, state = splited
            if state.startswith("connected"):
                changed_ifaces.append(iface_name)
                cmdlib.exec_cmd(
                    f"nmcli d set {iface_name} managed false".split(),
                    check=True,
                )
    yield
    for iface_name in changed_ifaces:
        cmdlib.exec_cmd(
            f"nmcli d set {iface_name} managed true".split(), check=True
        )


def test_do_not_use_unmanaged_iface_for_dns(all_unmanaged_with_gw_on_eth1):
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {DNS.SERVER: TEST_DNS_SRVS}}})

    assert_global_dns(TEST_DNS_SRVS)


@pytest.fixture
def all_unmanaged_with_gw_on_eth1_as_ext_mgt(all_unmanaged_with_gw_on_eth1):
    cmdlib.exec_cmd(
        "nmcli d set eth1 managed true".split(),
        check=True,
    )
    yield


def test_do_not_use_external_managed_iface_for_dns(
    all_unmanaged_with_gw_on_eth1_as_ext_mgt,
):
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {DNS.SERVER: TEST_DNS_SRVS}}})

    assert_global_dns(TEST_DNS_SRVS)


GLOBAL_DNS_CONF_FILE = "/var/lib/NetworkManager/NetworkManager-intern.conf"


def assert_global_dns(servers):
    with open(GLOBAL_DNS_CONF_FILE) as fd:
        content = fd.read()
        for server in servers:
            assert server in content


@pytest.fixture
def auto_eth1(eth1_up):
    libnmstate.apply(
        {
            DNS.KEY: {DNS.CONFIG: {DNS.SERVER: [], DNS.SEARCH: []}},
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                        InterfaceIPv4.AUTO_DNS: True,
                        InterfaceIPv4.AUTO_ROUTES: True,
                        InterfaceIPv4.AUTO_GATEWAY: True,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTO_DNS: True,
                        InterfaceIPv6.AUTO_ROUTES: True,
                        InterfaceIPv6.AUTO_GATEWAY: True,
                    },
                }
            ],
        }
    )
    yield
    libnmstate.apply(
        {
            DNS.KEY: {DNS.CONFIG: {DNS.SERVER: [], DNS.SEARCH: []}},
        }
    )


def test_static_dns_search_with_auto_dns(auto_eth1):
    libnmstate.apply(
        {
            DNS.KEY: {
                DNS.CONFIG: {DNS.SEARCH: ["example.org", "example.net"]}
            },
        }
    )
    output = cmdlib.exec_cmd(
        "nmcli -t -f ipv6.dns-search c show eth1".split(), check=True
    )[1]
    assert "ipv6.dns-search:example.org,example.net" in output


def test_purge_global_dns():
    desired_state = {
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: ["8.8.8.8", "2001:4860:4860::8888", "1.1.1.1"],
            }
        },
    }
    libnmstate.apply(desired_state)
    libnmstate.apply(
        {
            DNS.KEY: {DNS.CONFIG: {}},
        }
    )
    with open(GLOBAL_DNS_CONF_FILE) as fd:
        content = fd.read()
        for srv in desired_state[DNS.KEY][DNS.CONFIG][DNS.SERVER]:
            assert srv not in content


def test_global_dns_with_dns_options():
    try:
        libnmstate.apply(
            {
                DNS.KEY: {
                    DNS.CONFIG: {
                        DNS.SERVER: ["8.8.8.8", "2620:fe::9", "1.1.1.1"],
                        DNS.SEARCH: ["example.org", "example.net"],
                        DNS.OPTIONS: ["rotate", "debug"],
                    }
                },
            }
        )
    finally:
        libnmstate.apply(
            {
                DNS.KEY: {DNS.CONFIG: {}},
            }
        )


@pytest.fixture
def static_iface_dns():
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.IPV4: {
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: "192.0.2.251",
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                    InterfaceIPv4.DHCP: False,
                    InterfaceIPv4.ENABLED: True,
                },
            },
        ],
        Route.KEY: {
            Route.CONFIG: [
                {
                    Route.DESTINATION: "0.0.0.0/0",
                    Route.METRIC: 200,
                    Route.NEXT_HOP_ADDRESS: "192.0.2.1",
                    Route.NEXT_HOP_INTERFACE: "eth1",
                },
            ]
        },
        DNS.KEY: {
            DNS.CONFIG: {
                DNS.SERVER: ["8.8.8.8", "1.1.1.1"],
            }
        },
    }
    libnmstate.apply(desired_state)
    yield desired_state


def test_global_dns_do_not_touch_iface_dns(static_iface_dns):
    state = static_iface_dns
    original_dns_servers = copy.deepcopy(
        state[DNS.KEY][DNS.CONFIG][DNS.SERVER]
    )
    state[DNS.KEY][DNS.CONFIG][DNS.SERVER].reverse()

    libnmstate.apply(
        {
            DNS.KEY: {
                DNS.CONFIG: state[DNS.KEY][DNS.CONFIG],
            },
        }
    )
    # Apply the same configure twice is key reproducer of
    # https://issues.redhat.com/browse/RHEL-42487
    libnmstate.apply(
        {
            DNS.KEY: {
                DNS.CONFIG: state[DNS.KEY][DNS.CONFIG],
            },
        }
    )

    assert_global_dns(state[DNS.KEY][DNS.CONFIG])
    output = cmdlib.exec_cmd(
        "nmcli -g ipv4.dns c show eth1".split(), check=True
    )[1]
    assert output.strip() == ",".join(original_dns_servers)


# Adapted reproducer for https://issues.redhat.com/browse/RHEL-31095
def test_keep_interface_dns_when_not_changing_global_dns(static_iface_dns):
    # Apply changes to connection that are not related to DNS
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: ETH1,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: False,
                    },
                },
            ],
        }
    )

    # Check the nameserver is still there
    output = cmdlib.exec_cmd(
        f"nmcli -t -f ipv4.dns c show {ETH1}".split(), check=True
    )[1]
    assert "ipv4.dns:8.8.8.8,1.1.1.1" in output
