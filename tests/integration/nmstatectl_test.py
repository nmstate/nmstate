#
# Copyright 2018-2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import json
import os.path

from libnmstate.schema import Constants

from .testlib import cmd as libcmd
from .testlib.examplelib import find_examples_dir


SET_CMD = ['nmstatectl', 'set']
SHOW_CMD = ['nmstatectl', 'show']

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


def test_set_command_with_two_states():
    examples = find_examples_dir()
    cmd = SET_CMD + [os.path.join(examples, 'linuxbridge_creation.yml'),
                     os.path.join(examples, 'linuxbridge_deletion.yml')]
    ret = libcmd.exec_cmd(cmd)
    rc = ret[0]

    assert rc == RC_SUCCESS, format_exec_cmd_result(ret)


def format_exec_cmd_result(result):
    return 'rc={}, out={}, err={}'.format(*result)
