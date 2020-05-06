#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
import time


from libnmstate import __version__
from libnmstate.error import NmstateConflictError
from libnmstate.schema import Constants

from .testlib import assertlib
from .testlib import cmdlib
from .testlib.examplelib import example_state
from .testlib.examplelib import find_examples_dir
from .testlib.examplelib import load_example


SET_CMD = ["nmstatectl", "set"]
SHOW_CMD = ["nmstatectl", "show"]
CONFIRM_CMD = ["nmstatectl", "commit"]
ROLLBACK_CMD = ["nmstatectl", "rollback"]

LOOPBACK_JSON_CONFIG = """        {
            "name": "lo",
            "type": "unknown",
            "state": "down",
            "ipv4": {
                "enabled": false
            },
            "ipv6": {
                "enabled": false
            },
            "lldp": {
                "enabled": false
            },
            "mtu": 65536
        }"""

LOOPBACK_YAML_CONFIG = """- name: lo
  type: unknown
  state: down
  ipv4:
    enabled: false
  ipv6:
    enabled: false
  lldp:
    enabled: false
  mtu: 65536"""

ETH1_YAML_CONFIG = b"""interfaces:
- name: eth1
  state: up
  type: ethernet
  mtu: 1500
  ipv4:
    address:
    - ip: 192.0.2.250
      prefix-length: 24
    enabled: true
  ipv6:
    enabled: false
"""

EXAMPLES = find_examples_dir()
CONFIRMATION_INTERFACE = "eth1.101"
CONFIRMATION_CLEAN = "vlan101_eth1_absent.yml"
CONFIRMATION_TEST = "vlan101_eth1_up.yml"
CONFIRMATION_TEST_STATE = load_example(CONFIRMATION_TEST)
CONFIRMATION_SET = SET_CMD + [
    "--no-commit",
    os.path.join(EXAMPLES, CONFIRMATION_TEST),
]
CONFIRMATION_TIMEOUT = 5
CONFIRMATION_TIMOUT_COMMAND = SET_CMD + [
    "--no-commit",
    "--timeout",
    str(CONFIRMATION_TIMEOUT),
    os.path.join(EXAMPLES, CONFIRMATION_TEST),
]


def test_missing_operation():
    cmds = ["nmstatectl", "no-such-oper"]
    ret = cmdlib.exec_cmd(cmds)
    rc, out, err = ret

    assert rc == cmdlib.RC_FAIL2, cmdlib.format_exec_cmd_result(ret)
    assert "nmstatectl: error: invalid choice: 'no-such-oper'" in err


def test_show_command_with_json():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--json"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert LOOPBACK_JSON_CONFIG in out

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) > 1


def test_show_command_with_yaml_format():
    ret = cmdlib.exec_cmd(SHOW_CMD)
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert LOOPBACK_YAML_CONFIG in out


def test_show_command_json_only_lo():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--json", "lo"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) == 1
    assert state[Constants.INTERFACES][0]["name"] == "lo"


def test_show_command_only_non_existing():
    ret = cmdlib.exec_cmd(SHOW_CMD + ["--json", "non_existing_interface"])
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) == 0


def test_set_command_with_yaml_format():
    ret = cmdlib.exec_cmd(SET_CMD, stdin=ETH1_YAML_CONFIG)
    rc, out, err = ret

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)


def test_set_command_with_two_states():
    examples = find_examples_dir()
    cmd = SET_CMD + [
        os.path.join(examples, "linuxbrige_eth1_up.yml"),
        os.path.join(examples, "linuxbrige_eth1_absent.yml"),
    ]
    ret = cmdlib.exec_cmd(cmd)
    rc = ret[0]

    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)


def test_manual_confirmation(eth1_up):
    """ I can manually confirm a state. """

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN):

        assert_command(CONFIRMATION_SET)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)
        assert_command(CONFIRM_CMD)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)


def test_manual_rollback(eth1_up):
    """ I can manually roll back a state. """

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN) as clean_state:

        assert_command(CONFIRMATION_SET)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)
        assert_command(ROLLBACK_CMD)
        assertlib.assert_state(clean_state)


def test_dual_change(eth1_up):
    """ I cannot set a state without confirming/rolling back the state change.
    """

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN) as clean_state:

        assert_command(CONFIRMATION_SET)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)

        try:
            cmdlib.exec_cmd(CONFIRMATION_SET)
        except Exception as e:
            assert isinstance(e, NmstateConflictError)
        finally:
            assert_command(ROLLBACK_CMD)
            assertlib.assert_state(clean_state)


def test_automatic_rollback(eth1_up):
    """ If I do not confirm the state, it is automatically rolled back. """

    with example_state(CONFIRMATION_CLEAN, CONFIRMATION_CLEAN) as clean_state:

        assert_command(CONFIRMATION_TIMOUT_COMMAND)
        assertlib.assert_state(CONFIRMATION_TEST_STATE)

        time.sleep(CONFIRMATION_TIMEOUT)
        assertlib.assert_state(clean_state)


def test_version_argument():
    ret = cmdlib.exec_cmd(("nmstatectl", "--version"))
    rc, out, _ = ret
    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert out.rstrip() == __version__


def test_version_command():
    ret = cmdlib.exec_cmd(("nmstatectl", "version"))
    rc, out, _ = ret
    assert rc == cmdlib.RC_SUCCESS, cmdlib.format_exec_cmd_result(ret)
    assert out.rstrip() == __version__


def assert_command(cmd, expected_rc=cmdlib.RC_SUCCESS):
    ret = cmdlib.exec_cmd(cmd)
    returncode = ret[0]

    assert returncode == expected_rc, cmdlib.format_exec_cmd_result(ret)
    return ret
