#
# Copyright (c) 2018-2021 Red Hat, Inc.
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

import json
import os
import pytest
import time
import yaml

import libnmstate
from libnmstate import __version__
from libnmstate.error import NmstateConflictError
from libnmstate.schema import Constants
from libnmstate.schema import Route
from libnmstate.schema import RouteRule
from libnmstate.schema import DNS

from .testlib import assertlib
from .testlib import cmdlib
from .testlib.examplelib import example_state
from .testlib.examplelib import find_examples_dir
from .testlib.examplelib import load_example
from .testlib.statelib import state_match


APPLY_CMD = ["nmstatectl", "apply"]
SET_CMD = ["nmstatectl", "set"]
SHOW_CMD = ["nmstatectl", "show"]
CONFIRM_CMD = ["nmstatectl", "commit"]
ROLLBACK_CMD = ["nmstatectl", "rollback"]

LOOPBACK_CONFIG = {
    "name": "lo",
    "type": "unknown",
    "state": "up",
    "accept-all-mac-addresses": False,
    "ipv4": {
        "enabled": True,
        "address": [{"ip": "127.0.0.1", "prefix-length": 8}],
    },
    "ipv6": {
        "enabled": True,
        "address": [{"ip": "::1", "prefix-length": 128}],
    },
    "mac-address": "00:00:00:00:00:00",
    "mtu": 65536,
}

ETH1_YAML_CONFIG = b"""interfaces:
- name: eth1
  state: up
  type: ethernet
  accept-all-mac-addresses: false
  ipv4:
    address:
    - ip: 192.0.2.250
      prefix-length: 24
    enabled: true
  ipv6:
    enabled: false
  mtu: 1500
"""

SET_WARNING = "Using 'set' is deprecated, use 'apply' instead."

EXAMPLES = find_examples_dir()
CONFIRMATION_INTERFACE = "eth1.101"
CONFIRMATION_CLEAN = "vlan101_eth1_absent.yml"
CONFIRMATION_TEST = "vlan101_eth1_up.yml"
CONFIRMATION_TEST_STATE = load_example(CONFIRMATION_TEST)
CONFIRMATION_APPLY = APPLY_CMD + [
    "--no-commit",
    os.path.join(EXAMPLES, CONFIRMATION_TEST),
]
CONFIRMATION_TIMEOUT = 5
CONFIRMATION_TIMOUT_COMMAND = APPLY_CMD + [
    "--no-commit",
    "--timeout",
    str(CONFIRMATION_TIMEOUT),
    os.path.join(EXAMPLES, CONFIRMATION_TEST),
]


def test_missing_operation():
    cmds = ["nmstatectl", "no-such-oper"]
    ret = cmdlib.exec_cmd(cmds)
    rc, out, err = ret

    assert rc != cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert (
        # Python CLI
        "nmstatectl: error: invalid choice: 'no-such-oper'" in err
        or "'no-such-oper' which wasn't expected" in err
    )


def test_show_command_with_json():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--json"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    current_state = json.loads(out)
    state_match(LOOPBACK_CONFIG, current_state)
    assert len(current_state[Constants.INTERFACES]) > 1


def test_show_command_with_yaml_format():
    ret = cmdlib.exec_cmd(SHOW_CMD)
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    current_state = yaml.load(out)
    state_match(LOOPBACK_CONFIG, current_state)


def test_show_command_json_only(eth1_up):
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--json", "eth1"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) == 1
    assert state[Constants.INTERFACES][0]["name"] == "eth1"


def test_show_command_only_non_existing():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--json", "non_existing_interface"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) == 0


def test_show_command_with_long_running_config():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--running-config"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    current_state = yaml.load(out)
    state_match(LOOPBACK_CONFIG, current_state)


def test_show_command_with_long_show_secrets():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--show-secrets"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    current_state = yaml.load(out)
    state_match(LOOPBACK_CONFIG, current_state)


def test_show_command_with_short_running_config():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["-r"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    current_state = yaml.load(out)
    state_match(LOOPBACK_CONFIG, current_state)


def test_show_command_with_short_show_secrets():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["-s"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    current_state = yaml.load(out)
    state_match(LOOPBACK_CONFIG, current_state)


def test_apply_command_with_yaml_format():
    ret = cmdlib.exec_cmd(APPLY_CMD, stdin=ETH1_YAML_CONFIG)
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)


def test_set_command_with_yaml_deprecated():
    ret = cmdlib.exec_cmd(SET_CMD, stdin=ETH1_YAML_CONFIG)
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert SET_WARNING in err.rstrip()


def test_apply_command_with_two_states():
    examples = find_examples_dir()
    cmd = APPLY_CMD + [
        os.path.join(examples, "linuxbrige_eth1_up.yml"),
        os.path.join(examples, "linuxbrige_eth1_absent.yml"),
    ]
    ret = cmdlib.exec_cmd(cmd)
    rc = ret[0]

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assertlib.assert_absent("linux-br0")


def test_manual_confirmation(eth1_up):
    """I can manually confirm a state."""

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN):

        assert_command(CONFIRMATION_APPLY)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)
        assert_command(CONFIRM_CMD)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)


def test_manual_rollback(eth1_up):
    """I can manually roll back a state."""

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN) as clean_state:

        assert_command(CONFIRMATION_APPLY)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)
        assert_command(ROLLBACK_CMD)
        assertlib.assert_state(clean_state)


def test_dual_change(eth1_up):
    """
    I cannot apply a state without confirming/rolling back the state change.
    """

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN) as clean_state:

        assert_command(CONFIRMATION_APPLY)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)

        try:
            cmdlib.exec_cmd(CONFIRMATION_APPLY)
        except Exception as e:
            assert isinstance(e, NmstateConflictError)
        finally:
            assert_command(ROLLBACK_CMD)
            assertlib.assert_state(clean_state)


def test_automatic_rollback(eth1_up):
    """If I do not confirm the state, it is automatically rolled back."""

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN) as clean_state:

        assert_command(CONFIRMATION_TIMOUT_COMMAND)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)

        time.sleep(CONFIRMATION_TIMEOUT)
        assertlib.assert_state(clean_state)


def test_version_argument():
    ret = cmdlib.exec_cmd(("nmstatectl", "--version"))
    rc, out, _ = ret
    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert __version__ in out


def test_version_command():
    ret = cmdlib.exec_cmd(("nmstatectl", "version"))
    rc, out, _ = ret
    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert __version__ in out


def assert_command(cmd, expected_rc=cmdlib.RC_SUCCESS):
    ret = cmdlib.exec_cmd(cmd)
    returncode = ret[0]

    assert returncode == expected_rc, cmdlib.format_exec_cmd_result(ret)
    return ret


@pytest.fixture
def eth1_with_static_route_and_rule(eth1_up):
    desired_state = yaml.load(
        """---
        routes:
          config:
          - destination: 2001:db8:a::/64
            metric: 108
            next-hop-address: 2001:db8:1::2
            next-hop-interface: eth1
            table-id: 200
          - destination: 192.168.2.0/24
            metric: 108
            next-hop-address: 192.168.1.3
            next-hop-interface: eth1
            table-id: 200
        route-rules:
          config:
            - ip-from: 2001:db8:b::/64
              priority: 30000
              route-table: 200
            - ip-from: 192.168.3.2/32
              priority: 30001
              route-table: 200
        interfaces:
          - name: eth1
            type: ethernet
            state: up
            mtu: 1500
            ipv4:
              enabled: true
              dhcp: false
              address:
              - ip: 192.168.1.1
                prefix-length: 24
            ipv6:
              enabled: true
              dhcp: false
              autoconf: false
              address:
              - ip: 2001:db8:1::1
                prefix-length: 64
        """,
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    yield desired_state
    libnmstate.apply(
        {
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.NEXT_HOP_INTERFACE: "eth1",
                        Route.STATE: Route.STATE_ABSENT,
                    }
                ]
            },
            RouteRule.KEY: {
                RouteRule.CONFIG: [
                    {
                        RouteRule.STATE: RouteRule.STATE_ABSENT,
                    }
                ]
            },
            DNS.KEY: {DNS.CONFIG: {}},
        },
        verify_change=False,
    )


@pytest.mark.tier1
def test_show_iface_include_route_and_rule(eth1_with_static_route_and_rule):
    desired_state = eth1_with_static_route_and_rule
    output = cmdlib.exec_cmd(SHOW_CMD + ["eth1"], check=True)[1]
    new_state = yaml.load(output, Loader=yaml.SafeLoader)
    assert (
        desired_state[Route.KEY][Route.CONFIG]
        == new_state[Route.KEY][Route.CONFIG]
    )
    assert (
        desired_state[RouteRule.KEY][RouteRule.CONFIG]
        == new_state[RouteRule.KEY][RouteRule.CONFIG]
    )
