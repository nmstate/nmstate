# SPDX-License-Identifier: LGPL-2.1-or-later

import os
import shutil
from pathlib import Path

import yaml
import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .testlib.cmdlib import exec_cmd
from .testlib.assertlib import assert_absent
from .testlib.assertlib import assert_state_match
from .testlib.statelib import show_only

NMSTATE_CONF = """
[service]
keep_state_file_after_apply = true
"""

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

TEST_YAML3_CONTENT = """
capture:
  dummy_iface: interfaces.type == "dummy"
desired:
  interfaces:
  - name: "{{ capture.dummy_iface.interfaces.0.name }}"
    state: absent
"""

CONFIG_DIR = "/etc/nmstate"
NMSTATE_CONF_PATH = f"{CONFIG_DIR}/nmstate.conf"
TEST_CONFIG1_FILE_PATH = f"{CONFIG_DIR}/01-nmstate-test.yml"
TEST_CONFIG1_APPLIED_FILE_PATH = f"{CONFIG_DIR}/01-nmstate-test.applied"
TEST_CONFIG2_FILE_PATH = f"{CONFIG_DIR}/02-nmstate-test.yml"
TEST_CONFIG2_APPLIED_FILE_PATH = f"{CONFIG_DIR}/02-nmstate-test.applied"
TEST_CONFIG3_FILE_PATH = f"{CONFIG_DIR}/03-nmstate-policy-test.yml"
TEST_CONFIG3_APPLIED_FILE_PATH = f"{CONFIG_DIR}/03-nmstate-policy-test.applied"
DUMMY1 = "dummy1"


@pytest.fixture
def conf_do_not_delete_applied():
    if not os.path.isdir(CONFIG_DIR):
        os.mkdir(CONFIG_DIR)
    with open(NMSTATE_CONF_PATH, "w") as fd:
        fd.write(NMSTATE_CONF)
    yield
    os.remove(NMSTATE_CONF_PATH)


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
    for file in (
        TEST_CONFIG1_APPLIED_FILE_PATH,
        TEST_CONFIG2_APPLIED_FILE_PATH,
        TEST_CONFIG1_FILE_PATH,
        TEST_CONFIG2_FILE_PATH,
    ):
        if os.path.isfile(file):
            os.remove(file)


def test_nmstate_service_apply(nmstate_etc_config, conf_do_not_delete_applied):
    exec_cmd("systemctl restart nmstate".split(), check=True)

    desire_state = yaml.load(TEST_YAML2_CONTENT, Loader=yaml.SafeLoader)
    assert_state_match(desire_state)

    assert os.path.isfile(TEST_CONFIG1_FILE_PATH)
    assert (
        Path(TEST_CONFIG1_APPLIED_FILE_PATH).read_text()
        == Path(TEST_CONFIG1_FILE_PATH).read_text()
    )
    assert os.path.isfile(TEST_CONFIG2_FILE_PATH)
    assert (
        Path(TEST_CONFIG2_APPLIED_FILE_PATH).read_text()
        == Path(TEST_CONFIG2_FILE_PATH).read_text()
    )


@pytest.fixture
def dummy1_up():
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.UP,
                    Interface.TYPE: InterfaceType.DUMMY,
                }
            ]
        }
    )
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: DUMMY1,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


def test_nmstate_service_apply_nmpolicy(dummy1_up, conf_do_not_delete_applied):
    with open(TEST_CONFIG3_FILE_PATH, "w") as fd:
        fd.write(TEST_YAML3_CONTENT)

    current_state = show_only((DUMMY1,))
    assert current_state[Interface.KEY][0][Interface.NAME] == DUMMY1

    try:
        exec_cmd("systemctl restart nmstate".split(), check=True)
        assert_absent(DUMMY1)
        assert os.path.isfile(TEST_CONFIG3_FILE_PATH)
        assert (
            Path(TEST_CONFIG3_APPLIED_FILE_PATH).read_text()
            == Path(TEST_CONFIG3_FILE_PATH).read_text()
        )
    finally:
        os.remove(TEST_CONFIG3_APPLIED_FILE_PATH)
        os.remove(TEST_CONFIG3_FILE_PATH)


def test_nmstate_service_without_etc_folder():
    if os.path.isdir(CONFIG_DIR):
        shutil.rmtree(CONFIG_DIR, ignore_errors=True)

    exec_cmd("nmstatectl service".split(), check=True)


def test_nmstate_service_remove_applied_file_by_default(nmstate_etc_config):
    exec_cmd("systemctl restart nmstate".split(), check=True)

    desire_state = yaml.load(TEST_YAML2_CONTENT, Loader=yaml.SafeLoader)
    assert_state_match(desire_state)

    assert not os.path.isfile(TEST_CONFIG1_FILE_PATH)
    assert not os.path.isfile(TEST_CONFIG2_FILE_PATH)
    assert os.path.isfile(TEST_CONFIG1_APPLIED_FILE_PATH)
    assert os.path.isfile(TEST_CONFIG2_APPLIED_FILE_PATH)
