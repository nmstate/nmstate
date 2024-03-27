# SPDX-License-Identifier: LGPL-2.1-or-later
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
