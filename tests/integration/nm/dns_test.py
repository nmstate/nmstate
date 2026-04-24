# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

from ..testlib import assertlib
from ..testlib import cmdlib
from ..testlib.env import is_k8s
from ..testlib.env import nm_minor_version
from ..testlib.retry import retry_till_true_or_timeout
from ..testlib.yaml import load_yaml

DUMMY0 = "dummy0"
ETH1 = "eth1"

TEST_DNS_SRVS = ["192.0.2.2", "192.0.2.1"]
MIXED_DNS_SRVS = ["2001:db8:1::1", "192.0.2.9", "2001:db8:1::2"]
RETRY_TIMEOUT = 10


@pytest.fixture
def unmanaged_eth1_with_static_gw(eth1_env):
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
            check=True,
        )

        cmdlib.exec_cmd(
            f"ip addr del 192.0.2.2/24 dev {ETH1}".split(), check=True
        )
        cmdlib.exec_cmd(
            f"nmcli dev set {ETH1} managed yes".split(), check=True
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


@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
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


@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
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
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


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


@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
def test_global_dns_with_dns_options():
    try:
        libnmstate.apply(
            {
                DNS.KEY: {
                    DNS.CONFIG: {
                        DNS.SERVER: MIXED_DNS_SRVS,
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
def static_dns():
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {DNS.SERVER: TEST_DNS_SRVS}}})

    cur_dns_config = libnmstate.show()[DNS.KEY][DNS.CONFIG]
    assert cur_dns_config[DNS.SERVER] == TEST_DNS_SRVS

    yield
    libnmstate.apply(
        {
            DNS.KEY: {DNS.CONFIG: {}},
        }
    )


@pytest.mark.skipif(
    nm_minor_version() <= 47,
    reason="NM 1.47- does not support checkpoint on global dns",
)
@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
# kubernetes-nmstate depends on checkpoint to rollback to original state when
# check fails, hence tier1
@pytest.mark.tier1
def test_rollback_on_global_dns(static_dns):
    libnmstate.apply(
        {
            DNS.KEY: {
                DNS.CONFIG: {
                    # Mixing IPv6 and IPv4 name servers will force nmstate
                    # to use global DNS API of NetworkManager
                    DNS.SERVER: MIXED_DNS_SRVS,
                }
            },
        },
        commit=False,
    )

    assert_global_dns(MIXED_DNS_SRVS)

    libnmstate.rollback()

    def check_dns(srvs):
        cur_dns_config = libnmstate.show()[DNS.KEY][DNS.CONFIG]
        return cur_dns_config[DNS.SERVER] == srvs

    assert retry_till_true_or_timeout(RETRY_TIMEOUT, check_dns, TEST_DNS_SRVS)


@pytest.fixture
def clean_dns():
    yield
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {}}})


# https://issues.redhat.com/browse/RHEL-56557
@pytest.mark.tier1
@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
def test_reselect_iface_dns_if_desired(eth1_up):
    libnmstate.apply({DNS.KEY: {DNS.CONFIG: {DNS.SERVER: TEST_DNS_SRVS}}})
    assert_global_dns(TEST_DNS_SRVS)

    state = load_yaml(
        """---
        dns-resolver:
          config:
            server: {}
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            address:
            - ip: 192.0.2.251
              prefix-length: 24
            dhcp: false
            enabled: true
        """.format(
            TEST_DNS_SRVS
        )
    )

    libnmstate.apply(state)
    assert cmdlib.exec_cmd(
        "nmcli -g ipv4.dns c show eth1".split(), check=True
    )[1].strip() == ",".join(TEST_DNS_SRVS)


# https://issues.redhat.com/browse/RHEL-91250
@pytest.mark.tier1
@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
def test_write_both_global_dns_and_iface_dns(eth1_up):

    state = load_yaml(
        """---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          ipv4:
            dhcp: true
            auto-dns: false
            enabled: true
        """
    )
    state[DNS.KEY] = {DNS.CONFIG: {DNS.SERVER: TEST_DNS_SRVS}}

    libnmstate.apply(state)
    assert_global_dns(TEST_DNS_SRVS)
    assert cmdlib.exec_cmd(
        "nmcli -g ipv4.dns c show eth1".split(), check=True
    )[1].strip() == ",".join(TEST_DNS_SRVS)


# https://issues.redhat.com/browse/RHEL-102333
def test_set_dns_search_only_in_down_iface(auto_eth1, eth2_up):
    # Add a DNS search domain to a down interface
    cmdlib.exec_cmd("nmcli device down eth2".split(), check=True)
    cmdlib.exec_cmd("nmcli c modify eth2 ipv4.method auto".split(), check=True)
    cmdlib.exec_cmd(
        "nmcli c modify eth2 ipv4.dns-search 'example.com'".split(),
        check=True,
    )

    # Assert that the DNS searches configuration can change correctly
    libnmstate.apply(
        {
            DNS.KEY: {DNS.CONFIG: {DNS.SEARCH: ["example2.com"]}},
        }
    )

    # Assert that the old configuration has been purged from the down interface
    # and the new one hasn't been added to it.
    _r, search4, _e = cmdlib.exec_cmd(
        "nmcli -g ipv4.dns-search c show eth2".split(), check=True
    )
    _r, search6, _e = cmdlib.exec_cmd(
        "nmcli -g ipv6.dns-search c show eth2".split(), check=True
    )
    assert "example.com" not in search4 and "example.com" not in search6
    assert "example2.com" not in search4 and "example2.com" not in search6

    # It is not possible to assert that the new configuration has been put into
    # eth1 because, if there are more interfaces in the host, it might be in
    # any of them


@pytest.fixture
def eth1_static_iface_dns(eth1_up):
    cmdlib.exec_cmd("nmcli c del eth1".split(), check=False)
    cmdlib.exec_cmd(
        "nmcli c add type ethernet ifname eth1 "
        "connection.id eth1 ipv4.method manual "
        "ipv4.address 192.0.2.251/24 ipv4.gateway 192.0.2.1 "
        "ipv4.dns 192.0.2.1,192.0.2.2 "
        "ipv6.method disabled".split(),
        check=False,
    )
    yield
    cmdlib.exec_cmd("nmcli c del eth1".split())


# https://issues.redhat.com/browse/RHEL-125548
@pytest.mark.tier1
@pytest.mark.skipif(is_k8s(), reason="K8S cannot check global DNS file")
def test_use_global_dns_even_for_with_static_ip(
    eth1_static_iface_dns, eth2_up
):
    desired_state = load_yaml(
        """---
        interfaces:
        - name: eth2
          type: ethernet
          state: up
          ipv4:
            dhcp: false
            enabled: true
            address:
            - ip: 192.0.2.253
              prefix-length: 24
        routes:
          config:
          - destination: 0.0.0.0/0
            next-hop-address: 192.0.2.1
            next-hop-interface: eth2
            metric: 100
        dns-resolver:
          config:
            search:
            - example.net
            - example.org
            server:
            - 192.0.2.3
            - 192.0.2.4
        """
    )
    libnmstate.apply(desired_state)
    assert_global_dns(["192.0.2.3", "192.0.2.4"])
    # Make sure eth1 connection is untouched and still holding old DNS config
    assert (
        cmdlib.exec_cmd("nmcli -g ipv4.dns c show eth1".split())[1].strip()
        == "192.0.2.1,192.0.2.2"
    )
