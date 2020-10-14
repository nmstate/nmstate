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

from unittest import mock

from libnmstate.nmstate import show_with_plugins
from libnmstate.plugin import NmstatePlugin
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

TEST_IFACE1 = "nic1"
TEST_IFACE2 = "nic2"
TEST_IFACE3 = "nic3"


class TestPluginInfrastructure:
    def _gen_plugin_mocks(self):
        plugin_a = mock.MagicMock()
        plugin_a.priority = 10
        plugin_a.plugin_capabilities = [NmstatePlugin.PLUGIN_CAPABILITY_IFACE]
        plugin_a.is_supplemental_only = False
        plugin_b = mock.MagicMock()
        plugin_b.priority = 11
        plugin_b.plugin_capabilities = [NmstatePlugin.PLUGIN_CAPABILITY_IFACE]
        plugin_b.is_supplemental_only = False
        return [plugin_a, plugin_b]

    def test_show_with_plugins_merge_by_type_and_name(self):
        plugins = self._gen_plugin_mocks()
        plugins[0].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo1": "a",
            },
        ]

        plugins[1].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo2": "b",
            },
        ]
        assert show_with_plugins(plugins)[Interface.KEY] == [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo1": "a",
                "foo2": "b",
            }
        ]

    def test_show_with_plugins_merge_by_name_and_unknown_type(self):
        plugins = self._gen_plugin_mocks()
        plugins[0].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo1": "a",
            },
        ]

        plugins[1].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.UNKNOWN,
                "foo2": "b",
            },
        ]
        assert show_with_plugins(plugins)[Interface.KEY] == [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo1": "a",
                "foo2": "b",
            }
        ]

    def test_show_with_plugins_merge_by_name_without_type(self):
        plugins = self._gen_plugin_mocks()
        plugins[0].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo1": "a",
            },
        ]

        plugins[1].get_interfaces.return_value = [
            {Interface.NAME: TEST_IFACE1, "foo2": "b"},
        ]
        assert show_with_plugins(plugins)[Interface.KEY] == [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.ETHERNET,
                "foo1": "a",
                "foo2": "b",
            }
        ]

    def test_show_with_plugins_with_merge_with_duplicate_iface_names(self):
        plugins = self._gen_plugin_mocks()
        plugins[0].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo1": "a",
            },
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                "foo3": "c",
            },
        ]

        plugins[1].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo2": "b",
            },
        ]
        assert show_with_plugins(plugins)[Interface.KEY] == [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo1": "a",
                "foo2": "b",
            },
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                "foo3": "c",
            },
        ]

    def test_show_with_plugins_do_not_merge_if_not_uniqe(self):
        plugins = self._gen_plugin_mocks()
        plugins[0].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo1": "a",
            },
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                "foo3": "c",
            },
        ]

        plugins[1].get_interfaces.return_value = [
            {Interface.NAME: TEST_IFACE1, "foo2": "b"},
        ]
        assert show_with_plugins(plugins)[Interface.KEY] == [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo1": "a",
            },
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                "foo3": "c",
            },
            {Interface.NAME: TEST_IFACE1, "foo2": "b"},
        ]

    def test_show_with_plugins_remove_new_iface_from_supplemental_plugin(self):
        plugins = self._gen_plugin_mocks()
        plugins[0].is_supplemental_only = True
        plugins[0].get_interfaces.return_value = [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo1": "a",
            },
            {
                Interface.NAME: TEST_IFACE2,
                Interface.TYPE: InterfaceType.OVS_INTERFACE,
                "foo3": "c",
            },
        ]

        plugins[1].get_interfaces.return_value = [
            {Interface.NAME: TEST_IFACE1, "foo2": "b"},
        ]
        assert show_with_plugins(plugins)[Interface.KEY] == [
            {
                Interface.NAME: TEST_IFACE1,
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                "foo1": "a",
                "foo2": "b",
            },
        ]
