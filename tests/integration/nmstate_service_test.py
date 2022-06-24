#
# Copyright (c) 2022 Red Hat, Inc.
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

import os

import yaml
import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from .testlib.cmdlib import exec_cmd
from .testlib.assertlib import assert_state_match

TEST_YAML1_CONTENT = """
---
interfaces:
- name: dummy0
  type: dummy
  state: up
  ipv4:
    enabled: false
  ipv6:
    enabled: false
"""

TEST_YAML2_CONTENT = """
---
interfaces:
- name: dummy0
  type: dummy
  state: up
  ipv4:
    address:
    - ip: 192.0.2.252
      prefix-length: 24
    - ip: 192.0.2.251
      prefix-length: 24
    dhcp: false
    enabled: true
  ipv6:
    address:
      - ip: 2001:db8:2::1
        prefix-length: 64
      - ip: 2001:db8:1::1
        prefix-length: 64
    autoconf: false
    dhcp: false
    enabled: true
"""

CONFIG_DIR = "/etc/nmstate"
TEST_CONFIG1_FILE_PATH = f"{CONFIG_DIR}/01-nmstate-test.yml"
TEST_CONFIG1_APPLIED_FILE_PATH = f"{CONFIG_DIR}/01-nmstate-test.applied"
TEST_CONFIG2_FILE_PATH = f"{CONFIG_DIR}/02-nmstate-test.yml"
TEST_CONFIG2_APPLIED_FILE_PATH = f"{CONFIG_DIR}/02-nmstate-test.applied"


@pytest.fixture
def nmstate_etc_config():
    if not os.path.isdir(CONFIG_DIR):
        os.mkdir(CONFIG_DIR)

    for file_path, content in [
        (
            TEST_CONFIG1_FILE_PATH,
            TEST_YAML1_CONTENT,
        ),
        (
            TEST_CONFIG2_FILE_PATH,
            TEST_YAML2_CONTENT,
        ),
    ]:
        with open(file_path, "w") as fd:
            fd.write(content)
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "dummy0",
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )
    os.remove(TEST_CONFIG1_APPLIED_FILE_PATH)
    os.remove(TEST_CONFIG2_APPLIED_FILE_PATH)


def test_nmstate_service_apply(nmstate_etc_config):
    exec_cmd("systemctl start nmstate".split(), check=True)

    desire_state = yaml.load(TEST_YAML2_CONTENT, Loader=yaml.SafeLoader)
    assert_state_match(desire_state)

    assert not os.path.exists(TEST_CONFIG1_FILE_PATH)
    assert os.path.isfile(TEST_CONFIG1_APPLIED_FILE_PATH)
    assert not os.path.exists(TEST_CONFIG2_FILE_PATH)
    assert os.path.isfile(TEST_CONFIG2_APPLIED_FILE_PATH)
