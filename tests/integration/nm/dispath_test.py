# SPDX-License-Identifier: Apache-2.0

from contextlib import suppress
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
    state = load_yaml(
        """---
            interfaces:
            - name: eth1
              dispatch:
                post-activation: |
                  echo post-up-eth1 | systemd-cat
                post-deactivation: |
                  echo post-down-eth1 | systemd-cat
            """
    )
    libnmstate.apply(state)
    yield state


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


def test_add_dispatch_script(eth1_up):
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


TEST_DISPATCH_STATE_FILE_ETH1 = "/tmp/nmstate_test_dispatch_up_eth1"
TEST_DISPATCH_STATE_FILE_ETH2 = "/tmp/nmstate_test_dispatch_up_eth2"


def assert_dispatch_state_files(expected_content):
    with open(TEST_DISPATCH_STATE_FILE_ETH1) as fd:
        content = fd.read()
        assert content == expected_content

    with open(TEST_DISPATCH_STATE_FILE_ETH2) as fd:
        content = fd.read()
        assert content == expected_content


@pytest.fixture
def delete_dispatch_state_file():
    with suppress(FileNotFoundError):
        os.remove(TEST_DISPATCH_STATE_FILE_ETH1)
        os.remove(TEST_DISPATCH_STATE_FILE_ETH2)
    yield
    with suppress(FileNotFoundError):
        os.remove(TEST_DISPATCH_STATE_FILE_ETH1)
        os.remove(TEST_DISPATCH_STATE_FILE_ETH2)


@pytest.fixture
def eth1_eth2_with_old_dispatch_script(eth1_up, eth2_up):
    state = load_yaml(
        f"""---
            interfaces:
            - name: eth1
              dispatch:
                post-activation: |
                  echo -n old > {TEST_DISPATCH_STATE_FILE_ETH1}
            - name: eth2
              dispatch:
                post-activation: |
                  echo -n old > {TEST_DISPATCH_STATE_FILE_ETH2}
         """
    )
    libnmstate.apply(state)
    assert_dispatch_state_files("old")


def test_modify_dispatch_script(
    delete_dispatch_state_file, eth1_eth2_with_old_dispatch_script
):
    libnmstate.apply(
        load_yaml(
            f"""---
            interfaces:
            - name: eth1
              dispatch:
                post-activation: |
                  echo -n new > {TEST_DISPATCH_STATE_FILE_ETH1}
            - name: eth2
              dispatch:
                post-activation: |
                  echo -n new > {TEST_DISPATCH_STATE_FILE_ETH2}
         """
        ),
    )

    assert_dispatch_state_files("new")
