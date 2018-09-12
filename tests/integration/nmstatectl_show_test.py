#
# Copyright 2018 Red Hat, Inc.
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

from .testlib import cmd as libcmd


SHOW_CMD = ['nmstatectl', 'show']

RC_SUCCESS = 0
RC_FAIL2 = 2

LOOPBACK_JSON_CONFIG = b"""
        {
            "ipv4": {
                "enabled": false
            },
            "mtu": 65536,
            "name": "lo",
            "state": "down",
            "type": "unknown"
        }"""

LOOPBACK_YAML_CONFIG = b"""
- ipv4:
    enabled: false
  mtu: 65536
  name: lo
  state: down
  type: unknown"""


def test_missing_operation():
    cmds = ['nmstatectl', 'no-such-oper']
    ret = libcmd.exec_cmd(cmds)
    rc, out, err = ret

    assert_rc(rc, RC_FAIL2, ret)
    assert b"nmstatectl: error: invalid choice: 'no-such-oper'" in err


def test_show_command_with_no_flags():
    ret = libcmd.exec_cmd(SHOW_CMD)
    rc, out, err = ret

    assert_rc(rc, RC_SUCCESS, ret)
    assert LOOPBACK_JSON_CONFIG in out


def test_show_command_with_yaml_format():
    ret = libcmd.exec_cmd(SHOW_CMD + ['--yaml'])
    rc, out, err = ret

    assert_rc(rc, RC_SUCCESS, ret)
    assert LOOPBACK_YAML_CONFIG in out


def assert_rc(actual, expected, return_tuple):
    assert actual == expected, 'rc={}, out={}, err={}'.format(*return_tuple)
