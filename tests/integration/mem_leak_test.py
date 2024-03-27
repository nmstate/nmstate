# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2020 Red Hat, Inc.
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

import logging
import os
import time

import pytest

import libnmstate

from .testlib import ifacelib


def get_current_open_fd():
    time.sleep(0.1)  # Wait sysfs/proc been updated.
    return len(os.listdir("/proc/self/fd"))


@pytest.fixture(scope="function")
def disable_logging():
    logger = logging.getLogger()
    logger.disabled = True
    try:
        yield
    finally:
        logger.disabled = False


@pytest.mark.tier1
def test_libnmstate_show_fd_leak(disable_logging):
    original_fd = get_current_open_fd()
    for x in range(0, 100):
        libnmstate.show()
    assert get_current_open_fd() <= original_fd


@pytest.mark.tier1
def test_libnmstate_apply_fd_leak(disable_logging):
    original_fd = get_current_open_fd()
    for x in range(0, 10):
        with ifacelib.iface_up("eth1"):
            pass
    assert get_current_open_fd() <= original_fd
