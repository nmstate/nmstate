# SPDX-License-Identifier: Apache-2.0

import os

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import HostNameState

from .testlib import cmdlib

TEST_HOSTNAME1 = "nmstate-test1.example.org"
TEST_HOSTNAME2 = "nmstate-test2.example.org"


@pytest.fixture
def restore_hostname():
    cur_hostname_conf = libnmstate.show()[HostNameState.KEY]
    yield
    libnmstate.apply({HostNameState.KEY: cur_hostname_conf})


@pytest.mark.tier1
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="NM cannot change hostname in container",
)
def test_hostname_set_chg_and_clear(restore_hostname):
    libnmstate.apply(
        {
            HostNameState.KEY: {
                HostNameState.CONFIG: TEST_HOSTNAME1,
            }
        }
    )
    cur_host_name = cmdlib.exec_cmd(["hostname"], check=True)[1]
    assert os.path.exists("/etc/hostname")
    assert cur_host_name.strip() == TEST_HOSTNAME1
    libnmstate.apply(
        {
            HostNameState.KEY: {
                HostNameState.RUNNING: TEST_HOSTNAME2,
                HostNameState.CONFIG: "",
            }
        }
    )
    cur_host_name = cmdlib.exec_cmd(["hostname"], check=True)[1]
    assert cur_host_name.strip() == TEST_HOSTNAME2
    assert not os.path.exists("/etc/hostname")


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="NM cannot change hostname in container",
)
def test_hostname_set_config_in_memory_only(restore_hostname):
    with pytest.raises(NmstateVerificationError):
        libnmstate.apply(
            {
                HostNameState.KEY: {
                    HostNameState.RUNNING: TEST_HOSTNAME2,
                    HostNameState.CONFIG: TEST_HOSTNAME2,
                }
            },
            save_to_disk=False,
        )


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="NM cannot change hostname in container",
)
def test_hostname_set_in_memory_only(restore_hostname):
    libnmstate.apply(
        {
            HostNameState.KEY: {
                HostNameState.RUNNING: TEST_HOSTNAME2,
            }
        },
    )
    cur_host_name = cmdlib.exec_cmd(["hostname"], check=True)[1]
    assert cur_host_name.strip() == TEST_HOSTNAME2


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="NM cannot change hostname in container",
)
def test_hostname_set_different_running_and_config(restore_hostname):
    libnmstate.apply(
        {
            HostNameState.KEY: {
                HostNameState.RUNNING: TEST_HOSTNAME1,
                HostNameState.CONFIG: TEST_HOSTNAME2,
            }
        },
    )
    cur_host_name = cmdlib.exec_cmd(["hostname"], check=True)[1]
    assert cur_host_name.strip() == TEST_HOSTNAME1
    assert (
        cmdlib.exec_cmd(["cat", "/etc/hostname"], check=True)[1].strip()
        == TEST_HOSTNAME2
    )
