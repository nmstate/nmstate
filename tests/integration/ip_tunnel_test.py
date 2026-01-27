# SPDX-License-Identifier: Apache-2.0

import pytest

import libnmstate

from .testlib import assertlib
from .testlib.iptunnellib import ip_tunnel_interface

IP_TUNNEL0 = "ip_tunnel_test0"
ETH1 = "eth1"


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
