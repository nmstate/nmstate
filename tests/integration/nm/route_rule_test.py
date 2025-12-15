# SPDX-License-Identifier: Apache-2.0

import libnmstate
import pytest
import yaml

from ..testlib.cmdlib import exec_cmd


@pytest.fixture
def cleanup_loopback():
    yield
    libnmstate.apply(
        yaml.load(
            """---
            interfaces:
            - name: lo
              type: loopback
              state: absent
            """,
            Loader=yaml.SafeLoader,
        )
    )


def test_store_route_table_local_rule_to_loopback(cleanup_loopback):
    libnmstate.apply(
        yaml.load(
            """---
            route-rules:
              config:
                - route-table: 255
                  priority: 12345
                  family: ipv4
                - route-table: 255
                  priority: 12346
                  family: ipv6
            """,
            Loader=yaml.SafeLoader,
        )
    )

    assert (
        exec_cmd("nmcli -g ipv4.routing-rules c show lo".split())[1].strip()
        == "priority 12345 from 0.0.0.0/0 table 255"
    )

    assert (
        exec_cmd("nmcli -g ipv6.routing-rules c show lo".split())[1].strip()
        == r"priority 12346 from \:\:/0 table 255"
    )
