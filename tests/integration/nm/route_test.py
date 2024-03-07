# SPDX-License-Identifier: LGPL-2.1-or-later

from libnmstate.schema import Route
import libnmstate
import pytest
import yaml

from ..testlib.cmdlib import exec_cmd
from ..testlib.env import nm_minor_version
from ..testlib.route import assert_routes

from libnmstate.error import NmstateVerificationError

TEST_GATEAY4 = "192.0.2.1"
TEST_GATEAY6 = "2001:db8:2::"


@pytest.fixture
def eth1_with_old_gateway_format():
    libnmstate.apply(
        yaml.load(
            """---
            dns-resolver:
              config: {}
            interfaces:
            - name: eth1
              state: up
              mtu: 1500
              ipv4:
                address:
                - ip: 192.0.2.252
                  prefix-length: 24
                dhcp: false
                enabled: true
              ipv6:
                address:
                  - ip: 2001:db8:2::1
                    prefix-length: 64
                autoconf: false
                dhcp: false
                enabled: true
            """,
            Loader=yaml.SafeLoader,
        )
    )
    exec_cmd(
        f"nmcli c modify eth1 ipv4.gateway {TEST_GATEAY4} "
        f"ipv6.gateway {TEST_GATEAY6}".split(),
        check=True,
    )
    exec_cmd("nmcli c up eth1".split(), check=True)


def test_preserve_old_gateway(eth1_with_old_gateway_format):
    libnmstate.apply(
        yaml.load(
            """---
            dns-resolver:
              config:
                server:
                - 2001:4860:4860::8888
                - 8.8.8.8
            """,
            Loader=yaml.SafeLoader,
        )
    )
    cur_state = libnmstate.show()
    assert_routes(
        [
            {
                Route.NEXT_HOP_INTERFACE: "eth1",
                Route.DESTINATION: "0.0.0.0/0",
                Route.NEXT_HOP_ADDRESS: TEST_GATEAY4,
            },
            {
                Route.NEXT_HOP_INTERFACE: "eth1",
                Route.DESTINATION: "::/0",
                Route.NEXT_HOP_ADDRESS: TEST_GATEAY6,
            },
        ],
        cur_state,
    )


@pytest.mark.skipif(
    nm_minor_version() <= 42,
    reason="NM does not wait DHCP to assign static route",
)
@pytest.mark.tier1
def test_route_delayed_by_nm_fails(eth1_up):
    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(
            yaml.load(
                """---
                routes:
                  config:
                  - destination: 203.0.113.0/24
                    next-hop-address: 192.0.2.251
                    next-hop-interface: eth1
                interfaces:
                - name: eth1
                  state: up
                  ipv4:
                    dhcp: true
                    enabled: true
                """,
                Loader=yaml.SafeLoader,
            )
        )
