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
import copy

import pytest

from unittest import mock

from libnmstate import netapplier
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

BOND_TYPE = InterfaceType.BOND


@pytest.fixture
def show_with_plugins_mock():
    with mock.patch.object(netapplier, "show_with_plugins") as m:
        yield m


@pytest.fixture
def plugin_context_mock():
    with mock.patch.object(netapplier, "plugin_context") as m:
        #        def enter(self):
        #            return [mock.MagicMock()]
        #
        #        m().__enter__ = enter
        yield m


@pytest.fixture
def net_state_mock():
    with mock.patch.object(netapplier, "NetState") as m:
        yield m


def test_iface_admin_state_change(
    show_with_plugins_mock,
    plugin_context_mock,
    net_state_mock,
):
    current_config = {
        Interface.KEY: [
            {
                Interface.NAME: "foo",
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    desired_config = copy.deepcopy(current_config)

    desired_config[Interface.KEY][0][Interface.STATE] = InterfaceState.DOWN
    show_with_plugins_mock.return_value = current_config
    plugin = mock.MagicMock()
    plugin_context_mock.return_value.__enter__.return_value = [plugin]
    netapplier.apply(desired_config, verify_change=False)

    plugin.apply_changes.assert_called_with(
        net_state_mock(desired_config, current_config), True
    )


def test_add_new_bond(
    plugin_context_mock,
    show_with_plugins_mock,
    net_state_mock,
):
    show_with_plugins_mock.return_value = {}

    desired_config = {
        Interface.KEY: [
            {
                Interface.NAME: "bond99",
                Interface.TYPE: BOND_TYPE,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.PORT: [],
                    Bond.OPTIONS_SUBTREE: {"miimon": 200},
                },
                Interface.IPV4: {},
                Interface.IPV6: {},
            }
        ]
    }

    plugin = mock.MagicMock()
    plugin_context_mock.return_value.__enter__.return_value = [plugin]
    netapplier.apply(desired_config, verify_change=False)

    plugin.apply_changes.assert_called_with(
        net_state_mock(desired_config, {}), True
    )


def test_edit_existing_bond(
    show_with_plugins_mock,
    plugin_context_mock,
    net_state_mock,
):
    current_config = {
        Interface.KEY: [
            {
                Interface.NAME: "bond99",
                Interface.TYPE: BOND_TYPE,
                Interface.STATE: InterfaceState.UP,
                Bond.CONFIG_SUBTREE: {
                    Bond.MODE: BondMode.ROUND_ROBIN,
                    Bond.PORT: [],
                    Bond.OPTIONS_SUBTREE: {"miimon": "100"},
                },
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    show_with_plugins_mock.return_value = current_config

    desired_config = copy.deepcopy(current_config)
    options = desired_config[Interface.KEY][0][Bond.CONFIG_SUBTREE][
        Bond.OPTIONS_SUBTREE
    ]
    options["miimon"] = 200

    plugin = mock.MagicMock()
    plugin_context_mock.return_value.__enter__.return_value = [plugin]
    netapplier.apply(desired_config, verify_change=False)

    plugin.apply_changes.assert_called_with(
        net_state_mock(desired_config, current_config), True
    )


def test_error_apply():
    with pytest.raises(TypeError):
        # pylint: disable=too-many-function-args
        netapplier.apply({"interfaces": []}, True)
        # pylint: enable=too-many-function-args

    with pytest.raises(TypeError):
        # pylint: disable=too-many-function-args
        netapplier.apply({"interfaces": []}, True, True, 0)
        # pylint: enable=too-many-function-args


def test_error_commit():
    with pytest.raises(TypeError):
        # pylint: disable=too-many-function-args
        netapplier.commit(None)
        # pylint: enable=too-many-function-args


def test_error_rollback():
    with pytest.raises(TypeError):
        # pylint: disable=too-many-function-args
        netapplier.rollback(None)
        # pylint: enable=too-many-function-args
