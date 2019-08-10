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

import json
import os
import tempfile
import time
import shutil

import pytest

from libnmstate.schema import Constants

from .testlib import assertlib
from .testlib import cmd as libcmd
from .testlib.env import TEST_NIC1
from .testlib.examplelib import example_state
from .testlib.examplelib import find_examples_dir
from .testlib.examplelib import load_example


SET_CMD = ['nmstatectl', 'set']
SHOW_CMD = ['nmstatectl', 'show']
CONFIRM_CMD = ['nmstatectl', 'commit']
ROLLBACK_CMD = ['nmstatectl', 'rollback']

RC_SUCCESS = 0
RC_FAIL2 = 2

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
            "mtu": 65536
        }"""

LOOPBACK_YAML_CONFIG = """- name: lo
  type: unknown
  state: down
  ipv4:
    enabled: false
  ipv6:
    enabled: false
  mtu: 65536"""

ETH1_YAML_CONFIG = """interfaces:
- name: {}
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
""".format(
    TEST_NIC1
).encode()

CONFIRMATION_TIMEOUT = 5


def test_missing_operation():
    cmds = ['nmstatectl', 'no-such-oper']
    ret = libcmd.exec_cmd(cmds)
    rc, out, err = ret

    assert rc == RC_FAIL2, format_exec_cmd_result(ret)
    assert "nmstatectl: error: invalid choice: 'no-such-oper'" in err


def test_show_command_with_json():
    ret = libcmd.exec_cmd(SHOW_CMD + ['--json'])
    rc, out, err = ret

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)
    assert LOOPBACK_JSON_CONFIG in out

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) > 1


def test_show_command_with_yaml_format():
    ret = libcmd.exec_cmd(SHOW_CMD)
    rc, out, err = ret

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)
    assert LOOPBACK_YAML_CONFIG in out


def test_show_command_json_only_lo():
    ret = libcmd.exec_cmd(SHOW_CMD + ['--json', 'lo'])
    rc, out, err = ret

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) == 1
    assert state[Constants.INTERFACES][0]['name'] == 'lo'


def test_show_command_only_non_existing():
    ret = libcmd.exec_cmd(SHOW_CMD + ['--json', 'non_existing_interface'])
    rc, out, err = ret

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)

    state = json.loads(out)
    assert len(state[Constants.INTERFACES]) == 0


def test_set_command_with_yaml_format():
    ret = libcmd.exec_cmd(SET_CMD, stdin=ETH1_YAML_CONFIG)
    rc, out, err = ret

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)


@pytest.fixture(scope='module')
def setup_tmp_linux_bridge_state_files():
    files = []
    tmp_dir = tempfile.mkdtemp()
    examples = find_examples_dir()
    for file_name in ('linuxbrige_eth1_up.yml', 'linuxbrige_eth1_absent.yml'):
        tmp_file = os.path.join(tmp_dir, file_name)
        with open(os.path.join(examples, file_name), 'r') as fd:
            content = fd.read()
            with open(tmp_file, 'w') as tmp_fd:
                tmp_fd.write(content.replace('eth1', TEST_NIC1))

        files.append(tmp_file)
    yield files
    shutil.rmtree(tmp_dir)


def test_set_command_with_two_states(setup_tmp_linux_bridge_state_files):
    files = setup_tmp_linux_bridge_state_files
    cmd = SET_CMD + files
    ret = libcmd.exec_cmd(cmd)
    rc = ret[0]

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)


def test_manual_confirmation(setup_tmp_linux_bridge_state_files, test_nic1_up):
    """ I can manually confirm a state. """
    set_file, absent_file = setup_tmp_linux_bridge_state_files
    confirmation_clean = absent_file
    confirmation_set = SET_CMD + ['--no-commit', set_file]
    confirmation_test_state = load_example(set_file)

    with example_state(confirmation_clean, confirmation_clean):

        assert_command(confirmation_set)
        assertlib.assert_state(confirmation_test_state)
        assert_command(CONFIRM_CMD)
        assertlib.assert_state(confirmation_test_state)


def test_manual_rollback(setup_tmp_linux_bridge_state_files, test_nic1_up):
    """ I can manually roll back a state. """
    set_file, absent_file = setup_tmp_linux_bridge_state_files
    confirmation_set = SET_CMD + ['--no-commit', set_file]
    confirmation_test_state = load_example(set_file)

    with example_state(absent_file, absent_file) as clean_state:

        assert_command(confirmation_set)
        assertlib.assert_state(confirmation_test_state)
        assert_command(ROLLBACK_CMD)
        assertlib.assert_state(clean_state)


def test_dual_change(setup_tmp_linux_bridge_state_files, test_nic1_up):
    """ I cannot set a state without confirming/rolling back the state change.
    """
    set_file, absent_file = setup_tmp_linux_bridge_state_files
    confirmation_set = SET_CMD + ['--no-commit', set_file]
    confirmation_test_state = load_example(set_file)

    with example_state(absent_file, absent_file) as clean_state:

        assert_command(confirmation_set)
        assertlib.assert_state(confirmation_test_state)
        assert_command(confirmation_set, os.EX_UNAVAILABLE)

        assert_command(ROLLBACK_CMD)
        assertlib.assert_state(clean_state)


def test_automatic_rollback(setup_tmp_linux_bridge_state_files, test_nic1_up):
    """ If I do not confirm the state, it is automatically rolled back. """
    set_file, absent_file = setup_tmp_linux_bridge_state_files
    confirmation_set = SET_CMD + ['--no-commit', set_file]
    confirmation_test_state = load_example(set_file)
    confirmation_timout_command = confirmation_set + [
        '--timeout',
        str(CONFIRMATION_TIMEOUT),
    ]

    with example_state(absent_file, absent_file) as clean_state:

        assert_command(confirmation_timout_command)
        assertlib.assert_state(confirmation_test_state)
        time.sleep(CONFIRMATION_TIMEOUT)
        assertlib.assert_state(clean_state)


def assert_command(cmd, expected_rc=RC_SUCCESS):
    ret = libcmd.exec_cmd(cmd)
    returncode = ret[0]

    assert returncode == expected_rc, format_exec_cmd_result(ret)
    return ret


def format_exec_cmd_result(result):
    return 'rc={}, out={}, err={}'.format(*result)
