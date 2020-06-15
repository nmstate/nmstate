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
import pytest

from unittest import mock

from libnmstate import netinfo
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route
from libnmstate.schema import RouteRule


@pytest.fixture
def show_with_plugins_mock():
    with mock.patch.object(netinfo, "show_with_plugins") as m:
        yield m


@pytest.fixture
def plugin_context_mock():
    with mock.patch.object(netinfo, "plugin_context") as m:

        def enter(self):
            return self

        m().__enter__ = enter
        yield m


def test_netinfo_show(show_with_plugins_mock, plugin_context_mock):
    current_config = {
        DNS.KEY: {DNS.RUNNING: {}, DNS.CONFIG: {}},
        Route.KEY: {Route.CONFIG: [], Route.RUNNING: []},
        RouteRule.KEY: {RouteRule.CONFIG: []},
        Interface.KEY: [
            {
                Interface.NAME: "foo",
                Interface.TYPE: InterfaceType.UNKNOWN,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ],
    }

    show_with_plugins_mock.return_value = current_config
    report = netinfo.show()

    assert current_config == report


def test_error_show(show_with_plugins_mock, plugin_context_mock):
    current_config = {
        DNS.KEY: {DNS.RUNNING: {}, DNS.CONFIG: {}},
        Route.KEY: {"config": [], "running": []},
        RouteRule.KEY: {RouteRule.CONFIG: []},
        Interface.KEY: [
            {
                "name": "foo",
                "type": "unknown",
                "state": "up",
                "ipv4": {InterfaceIPv4.ENABLED: False},
                "ipv6": {InterfaceIPv6.ENABLED: False},
            }
        ],
    }
    show_with_plugins_mock.return_value = current_config

    with pytest.raises(TypeError):
        # pylint: disable=too-many-function-args
        netinfo.show(None)
        # pylint: enable=too-many-function-args
