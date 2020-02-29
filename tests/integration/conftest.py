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

import logging
import subprocess
import warnings
import os.path
import pytest

import libnmstate

from .testlib import ifacelib


REPORT_HEADER = """RPMs: {rpms}
OS: {osname}
nmstate: {nmstate_version}
"""


data_path = "failures.log"   # name of file containing details of errors


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    print(os.path)
    if rep.when == "call" and rep.failed:
        mode = "a" if os.path.exists(data_path) else "w"
        with open(data_path, mode) as f:
            f.write(rep.longreprtext + "\n")


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow is given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session", autouse=True)
def logging_setup():
    logging.basicConfig(
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
    )


@pytest.fixture(scope="session", autouse=True)
def ethx_init(diff_initial_state):
    """ Remove any existing definitions on the ethX interfaces. """
    ifacelib.ifaces_init("eth1", "eth2")


@pytest.fixture(scope="function")
def eth1_up():
    with ifacelib.iface_up("eth1") as ifstate:
        yield ifstate


@pytest.fixture(scope="function")
def eth2_up():
    with ifacelib.iface_up("eth2") as ifstate:
        yield ifstate


port0_up = eth1_up
port1_up = eth2_up


@pytest.fixture(scope="session", autouse=True)
def diff_initial_state():
    old_state = libnmstate.show()
    yield
    new_state = libnmstate.show()

    if old_state != new_state:
        warnings.warn(
            "Network state after test run does not match network state "
            "before test run:\n {}\n".format(
                libnmstate.prettystate.format_desired_current_state_diff(
                    old_state, new_state
                )
            )
        )


def pytest_report_header(config):
    return REPORT_HEADER.format(
        rpms=_get_package_nvr("NetworkManager"),
        osname=_get_osname(),
        nmstate_version=_get_nmstate_version(),
    )


def _get_nmstate_version():
    """
    Prefer RPM version of nmstate, if not found, use libnmstate module version
    """
    try:
        return _get_package_nvr("nmstate")
    except subprocess.CalledProcessError:
        return libnmstate.__version__


def _get_package_nvr(package):
    return (
        subprocess.check_output(["rpm", "-q", package]).strip().decode("utf-8")
    )


def _get_osname():
    with open("/etc/os-release") as os_release:
        for line in os_release.readlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", maxsplit=1)[1].strip().strip('"')
    return ""
