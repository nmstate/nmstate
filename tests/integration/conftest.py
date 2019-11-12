#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

import pytest

import libnmstate

from .testlib import ifacelib


REPORT_HEADER = """RPMs: {rpms}
OS: {osname}
"""


@pytest.fixture(scope='session', autouse=True)
def logging_setup():
    logging.basicConfig(
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
    )


@pytest.fixture(scope='session', autouse=True)
def ethx_init(preserve_old_config):
    """ Remove any existing definitions on the ethX interfaces. """
    ifacelib.ifaces_init('eth1', 'eth2')


@pytest.fixture(scope='function')
def eth1_up():
    with ifacelib.iface_up('eth1') as ifstate:
        yield ifstate


@pytest.fixture(scope='function')
def eth2_up():
    with ifacelib.iface_up('eth2') as ifstate:
        yield ifstate


port0_up = eth1_up
port1_up = eth2_up


@pytest.fixture(scope='session', autouse=True)
def preserve_old_config():
    old_state = libnmstate.show()
    yield
    libnmstate.apply(old_state, verify_change=False)


def pytest_report_header(config):
    _ = config
    return REPORT_HEADER.format(
        rpms=_get_package_nvr('NetworkManager'), osname=_get_osname()
    )


def _get_package_nvr(package):
    return (
        subprocess.check_output(['rpm', '-q', package]).strip().decode('utf-8')
    )


def _get_osname():
    with open('/etc/os-release') as os_release:
        for line in os_release.readlines():
            if line.startswith('PRETTY_NAME='):
                return line.split('=', maxsplit=1)[1].strip().strip('"')
    return ''
