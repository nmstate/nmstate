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

import pytest

from unittest import mock

from libnmstate import nm
from libnmstate import schema
from libnmstate.ifaces.ethernet import EthernetIface


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.wired, "NM") as m:
        yield m


def _create_ethernet_iface(info):
    iface = EthernetIface(info)
    iface.mark_as_desired()
    return iface


def test_create_setting_None(NM_mock):
    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {
                schema.Interface.NAME: "foo",
            }
        ),
        None,
    )
    assert setting is None


def test_create_setting_duplicate(NM_mock):
    base_profile = mock.MagicMock()

    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {
                schema.Interface.NAME: "foo",
                schema.Ethernet.CONFIG_SUBTREE: {schema.Ethernet.SPEED: 1000},
            }
        ),
        base_profile,
    )
    assert (
        setting
        == base_profile.get_setting_wired.return_value.duplicate.return_value
    )


def test_create_setting_mac(NM_mock):
    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {
                schema.Interface.NAME: "foo",
                schema.Interface.MAC: "01:23:45:67:89:ab",
            }
        ),
        None,
    )
    assert setting == NM_mock.SettingWired.new.return_value
    assert setting.props.cloned_mac_address == "01:23:45:67:89:ab"


def test_create_setting_mtu(NM_mock):
    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {schema.Interface.NAME: "foo", schema.Interface.MTU: 1500}
        ),
        None,
    )
    assert setting == NM_mock.SettingWired.new.return_value
    assert setting.props.mtu == 1500


def test_create_setting_auto_negotiation_False(NM_mock):
    iface = _create_ethernet_iface(
        {
            schema.Interface.NAME: "foo",
            schema.Ethernet.CONFIG_SUBTREE: {
                schema.Ethernet.AUTO_NEGOTIATION: False
            },
        }
    )
    iface.merge(
        EthernetIface(
            {
                schema.Interface.NAME: "foo",
                schema.Ethernet.CONFIG_SUBTREE: {
                    schema.Ethernet.AUTO_NEGOTIATION: False,
                    schema.Ethernet.SPEED: 1000,
                    schema.Ethernet.DUPLEX: schema.Ethernet.FULL_DUPLEX,
                },
            }
        )
    )
    setting = nm.wired.create_setting(
        iface,
        None,
    )
    assert setting == NM_mock.SettingWired.new.return_value
    assert setting.props.auto_negotiate is False
    assert setting.props.speed == 1000
    assert setting.props.duplex == schema.Ethernet.FULL_DUPLEX


def test_create_setting_only_auto_negotiation_True(NM_mock):
    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {
                schema.Interface.NAME: "foo",
                schema.Ethernet.CONFIG_SUBTREE: {
                    schema.Ethernet.AUTO_NEGOTIATION: True
                },
            }
        ),
        None,
    )
    assert setting == NM_mock.SettingWired.new.return_value
    assert setting.props.auto_negotiate is True
    assert setting.props.speed == 0
    assert setting.props.duplex is None


def test_create_setting_auto_negotiation_speed_duplex(NM_mock):
    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {
                schema.Interface.NAME: "foo",
                schema.Ethernet.CONFIG_SUBTREE: {
                    schema.Ethernet.AUTO_NEGOTIATION: True,
                    schema.Ethernet.SPEED: 1000,
                    schema.Ethernet.DUPLEX: schema.Ethernet.FULL_DUPLEX,
                },
            }
        ),
        None,
    )
    assert setting == NM_mock.SettingWired.new.return_value
    assert setting.props.auto_negotiate is True
    assert setting.props.speed == 0
    assert setting.props.duplex is None


def test_create_setting_speed_duplex(NM_mock):
    setting = nm.wired.create_setting(
        _create_ethernet_iface(
            {
                schema.Interface.NAME: "foo",
                schema.Ethernet.CONFIG_SUBTREE: {
                    schema.Ethernet.AUTO_NEGOTIATION: False,
                    schema.Ethernet.SPEED: 1000,
                    schema.Ethernet.DUPLEX: schema.Ethernet.FULL_DUPLEX,
                },
            }
        ),
        None,
    )
    assert setting == NM_mock.SettingWired.new.return_value
    assert setting.props.speed == 1000
    assert setting.props.duplex == schema.Ethernet.FULL_DUPLEX


class TestWiredSetting:
    def test_identity(self):
        state = {}
        obj1 = obj2 = nm.wired.WiredSetting(state)

        assert obj1 == obj2
        assert not (obj1 != obj2)

    def test_empty_state_is_false(self):
        state = {}
        obj = nm.wired.WiredSetting(state)

        assert not obj

    def test_no_relevant_keys_is_false(self):
        state = {"foo": "boo"}
        obj = nm.wired.WiredSetting(state)

        assert not obj

    def test_relevant_keys_with_false_values_is_false(self):
        state = {schema.Interface.MTU: 0, schema.Interface.MAC: ""}
        obj = nm.wired.WiredSetting(state)

        assert not obj

    def test_partial_relevant_keys_is_true(self):
        state = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        obj = nm.wired.WiredSetting(state)

        assert obj

    def test_equality_for_empty_states(self):
        state = {}
        obj1 = nm.wired.WiredSetting(state)
        obj2 = nm.wired.WiredSetting(state)

        assert obj1 == obj2
        assert not (obj1 != obj2)

    def test_equality_for_partial_states(self):
        state = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        obj1 = nm.wired.WiredSetting(state)
        obj2 = nm.wired.WiredSetting(state)

        assert obj1 == obj2
        assert not (obj1 != obj2)

    def test_inequality_for_partial_states(self):
        state1 = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        state2 = {schema.Interface.MTU: 1000, schema.Interface.MAC: "abc"}
        obj1 = nm.wired.WiredSetting(state1)
        obj2 = nm.wired.WiredSetting(state2)

        assert obj1 != obj2
        assert not (obj1 == obj2)

    def test_inequality_for_partial_states_with_missing_properties(self):
        state1 = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        state2 = {schema.Interface.MAC: "abc"}

        obj1 = nm.wired.WiredSetting(state1)
        obj2 = nm.wired.WiredSetting(state2)

        assert obj1 != obj2
        assert not (obj1 == obj2)

    def test_hash_unique(self):
        state = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        obj1 = nm.wired.WiredSetting(state)
        obj2 = nm.wired.WiredSetting(state)

        assert hash(obj1) == hash(obj2)

    def test_behaviour_with_set(self):
        state1 = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        state2 = {schema.Interface.MTU: 1500, schema.Interface.MAC: "abc"}
        state3 = {schema.Interface.MAC: "abc"}

        obj1 = nm.wired.WiredSetting(state1)
        obj2 = nm.wired.WiredSetting(state2)
        obj3 = nm.wired.WiredSetting(state3)

        assert 1 == len(set([obj1, obj2]))
        assert 2 == len(set([obj1, obj3]))
