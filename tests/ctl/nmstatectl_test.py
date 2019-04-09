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
from __future__ import absolute_import

import json
import subprocess

import six

from .compat import mock

from nmstatectl import nmstatectl

LO_JSON_STATE = """{
    "routes": {
        "config": [],
        "running": []
    },
    "interfaces": [
        {
            "name": "lo",
            "type": "unknown",
            "state": "down"
        }
    ]
}
"""

EMPTY_JSON_STATE = """{
    "routes": {
        "config": [],
        "running": []
    },
    "interfaces": []
}
"""

EMPTY_YAML_STATE = """---
routes:
  config: []
  running: []
interfaces: []
"""

LO_YAML_STATE = """---
routes:
  config: []
  running: []
interfaces:
- name: lo
  type: unknown
  state: down
"""


@mock.patch('sys.argv', ['nmstatectl', 'set', 'mystate.json'])
@mock.patch.object(nmstatectl.netapplier, 'apply',
                   lambda state, verify_change, commit, timeout: None)
@mock.patch.object(nmstatectl, 'open', mock.mock_open(read_data='{}'),
                   create=True)
def test_run_ctl_directly_set():
    nmstatectl.main()


@mock.patch('sys.argv', ['nmstatectl', 'show'])
@mock.patch.object(nmstatectl.netinfo, 'show', lambda: {})
def test_run_ctl_directly_show_empty():
    nmstatectl.main()


@mock.patch('sys.argv', ['nmstatectl', 'show', 'non_existing_interface'])
@mock.patch.object(
    nmstatectl.netinfo, 'show', lambda: json.loads(LO_JSON_STATE))
@mock.patch('nmstatectl.nmstatectl.sys.stdout', new_callable=six.StringIO)
def test_run_ctl_directly_show_only_empty(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == EMPTY_YAML_STATE


@mock.patch('sys.argv', ['nmstatectl', 'show', 'lo'])
@mock.patch.object(
    nmstatectl.netinfo, 'show', lambda: json.loads(LO_JSON_STATE))
@mock.patch('nmstatectl.nmstatectl.sys.stdout', new_callable=six.StringIO)
def test_run_ctl_directly_show_only(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == LO_YAML_STATE


@mock.patch('sys.argv', ['nmstatectl', 'show', '--json',
                         'non_existing_interface'])
@mock.patch.object(
    nmstatectl.netinfo, 'show', lambda: json.loads(LO_JSON_STATE))
@mock.patch('nmstatectl.nmstatectl.sys.stdout', new_callable=six.StringIO)
def test_run_ctl_directly_show_json_only_empty(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == EMPTY_JSON_STATE


@mock.patch('sys.argv', ['nmstatectl', 'show', '--json', 'lo'])
@mock.patch.object(
    nmstatectl.netinfo, 'show', lambda: json.loads(LO_JSON_STATE))
@mock.patch('nmstatectl.nmstatectl.sys.stdout', new_callable=six.StringIO)
def test_run_ctl_directly_show_json_only(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == LO_JSON_STATE


def test_run_ctl_executable():
    rc = subprocess.call(['nmstatectl', '--help'])
    assert rc == 0
