# SPDX-License-Identifier: Apache-2.0

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
