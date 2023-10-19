# SPDX-License-Identifier: Apache-2.0

import os

import pytest

import libnmstate

from ..testlib.yaml import load_yaml

NM_DISPATCH_FOLDER = "/etc/NetworkManager/dispatcher.d"


def gen_file_path(iface_name, action):
    return f"{NM_DISPATCH_FOLDER}/nmstate-{iface_name}-{action}.sh"


def assert_dispatch_script(iface_name, action, expected_content):
    file_path = gen_file_path(iface_name, action)
    with open(file_path, "r") as fd:
        content = fd.read()
    assert expected_content in content


def assert_dispatch_script_not_exist(iface_name, action):
    assert not os.path.exists(gen_file_path(iface_name, action))


@pytest.fixture
def eth1_up_with_dispatch_script(eth1_up):
    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: eth1
              dispatch:
                post-activation: |
                  echo post-up-eth1 | systemd-cat
                post-deactivation: |
                  echo post-down-eth1 | systemd-cat
            """
        ),
    )


def test_add_and_remove_dispatch_script(eth1_up_with_dispatch_script):
    assert_dispatch_script("eth1", "up", "echo post-up-eth1 | systemd-cat")
    assert_dispatch_script("eth1", "down", "echo post-down-eth1 | systemd-cat")

    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: eth1
              dispatch:
                post-activation: ''
                post-deactivation: ''
            """
        ),
    )
    assert_dispatch_script_not_exist("eth1", "up")
    assert_dispatch_script_not_exist("eth1", "down")


def test_remove_dispatch_script_on_iface_absent(eth1_up):
    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: eth1
              state: absent
            """
        ),
    )
    assert_dispatch_script_not_exist("eth1", "up")
    assert_dispatch_script_not_exist("eth1", "down")


def test_modify_dispatch_script(eth1_up):
    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: eth1
              dispatch:
                post-activation: |
                  echo new-post-up-eth1 | systemd-cat
                post-deactivation: |
                  echo new-post-down-eth1 | systemd-cat
            """
        ),
    )
    assert_dispatch_script("eth1", "up", "echo new-post-up-eth1 | systemd-cat")
    assert_dispatch_script(
        "eth1", "down", "echo new-post-down-eth1 | systemd-cat"
    )
