# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from .testlib import assertlib
from .testlib.cmdlib import exec_cmd
from .testlib.iptunnellib import ip_tunnel_interface

IP_TUNNEL0 = "ip_tunnel_test0"
GRETAP0 = "gretap_test0"
ETH1 = "eth1"


@pytest.fixture(scope="function")
def gretap_up():
    exec_cmd(
        [
            "ip",
            "link",
            "add",
            GRETAP0,
            "type",
            "gretap",
            "local",
            "192.0.2.1",
            "remote",
            "192.0.2.2",
        ],
        check=True,
    )
    try:
        yield
    finally:
        exec_cmd(["ip", "link", "del", GRETAP0])


# https://issues.redhat.com/browse/RHEL-79801
@pytest.mark.tier1
def test_add_ipip_tunnel_and_remove(eth1_up):
    with ip_tunnel_interface(
        IP_TUNNEL0,
        mode="ipip",
        local="192.0.2.1",
        remote="192.0.2.2",
        parent=ETH1,
        ttl=128,
        tos=42,
        path_mtu_discovery=True,
    ) as state:
        libnmstate.apply(state)
        assertlib.assert_state(state)
    assertlib.assert_absent(IP_TUNNEL0)


# https://issues.redhat.com/browse/RHEL-79801
@pytest.mark.tier1
def test_ip6ip6_tunnel_and_remove():
    with ip_tunnel_interface(
        IP_TUNNEL0,
        mode="ip6ip6",
        local="2001:db8::ffff",
        remote="2001:db8::1",
        flow_label=4224,
        encap_limit=8,
    ) as state:
        libnmstate.apply(state)
        assertlib.assert_state(state)
    assertlib.assert_absent(IP_TUNNEL0)


# https://issues.redhat.com/browse/RHEL-79801
@pytest.mark.tier1
def test_ipip6_tunnel_and_remove():
    with ip_tunnel_interface(
        IP_TUNNEL0,
        mode="ipip6",
        local="2001:db8::ffff",
        remote="2001:db8::1",
        ip6tun_flags=["ign-encap-limit"],
        flow_label=4224,
    ) as state:
        libnmstate.apply(state)
        assertlib.assert_state(state)
    assertlib.assert_absent(IP_TUNNEL0)


# https://issues.redhat.com/browse/RHEL-170926
@pytest.mark.tier1
def test_gretap_show(gretap_up):
    state = libnmstate.show()
    iface_names = [i[Interface.NAME] for i in state[Interface.KEY]]
    assert GRETAP0 in iface_names
    gretap_iface = next(
        i for i in state[Interface.KEY] if i[Interface.NAME] == GRETAP0
    )
    assert gretap_iface[Interface.TYPE] != InterfaceType.ETHERNET
