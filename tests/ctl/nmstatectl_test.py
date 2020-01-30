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
import io
import json
import subprocess

from unittest import mock

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


@mock.patch("sys.argv", ["nmstatectl", "set", "mystate.json"])
@mock.patch.object(
    nmstatectl.libnmstate,
    "apply",
    lambda state, verify_change=True, commit=True, rollback_timeout=60: None,
)
@mock.patch.object(
    nmstatectl, "open", mock.mock_open(read_data="{}"), create=True
)
def test_run_ctl_directly_set():
    nmstatectl.main()


@mock.patch("sys.argv", ["nmstatectl", "show"])
@mock.patch.object(nmstatectl.libnmstate, "show", lambda: {})
def test_run_ctl_directly_show_empty():
    nmstatectl.main()


@mock.patch("sys.argv", ["nmstatectl", "show", "non_existing_interface"])
@mock.patch.object(
    nmstatectl.libnmstate, "show", lambda: json.loads(LO_JSON_STATE)
)
@mock.patch("nmstatectl.nmstatectl.sys.stdout", new_callable=io.StringIO)
def test_run_ctl_directly_show_only_empty(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == EMPTY_YAML_STATE


@mock.patch("sys.argv", ["nmstatectl", "show", "lo"])
@mock.patch.object(
    nmstatectl.libnmstate, "show", lambda: json.loads(LO_JSON_STATE)
)
@mock.patch("nmstatectl.nmstatectl.sys.stdout", new_callable=io.StringIO)
def test_run_ctl_directly_show_only(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == LO_YAML_STATE


@mock.patch(
    "sys.argv", ["nmstatectl", "show", "--json", "non_existing_interface"]
)
@mock.patch.object(
    nmstatectl.libnmstate, "show", lambda: json.loads(LO_JSON_STATE)
)
@mock.patch("nmstatectl.nmstatectl.sys.stdout", new_callable=io.StringIO)
def test_run_ctl_directly_show_json_only_empty(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == EMPTY_JSON_STATE


@mock.patch("sys.argv", ["nmstatectl", "show", "--json", "lo"])
@mock.patch.object(
    nmstatectl.libnmstate, "show", lambda: json.loads(LO_JSON_STATE)
)
@mock.patch("nmstatectl.nmstatectl.sys.stdout", new_callable=io.StringIO)
def test_run_ctl_directly_show_json_only(mock_stdout):
    nmstatectl.main()
    assert mock_stdout.getvalue() == LO_JSON_STATE


def test_run_ctl_executable():
    rc = subprocess.call(["nmstatectl", "--help"])
    assert rc == 0
