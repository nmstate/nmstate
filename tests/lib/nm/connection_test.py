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

from libnmstate import nm


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.connection, "NM") as m:
        yield m


@pytest.fixture()
def context_mock():
    yield mock.MagicMock()


def test_create_setting(NM_mock):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create("con-name", "iface-name", "iface-type")

    assert con_setting.setting.props.id == "con-name"
    assert con_setting.setting.props.interface_name == "iface-name"
    assert con_setting.setting.props.uuid
    assert con_setting.setting.props.type == "iface-type"
    assert con_setting.setting.props.autoconnect is True
    assert con_setting.setting.props.autoconnect_slaves == (
        NM_mock.SettingConnectionAutoconnectSlaves.YES
    )


def test_set_controller_setting():
    con_setting = nm.connection.ConnectionSetting(mock.MagicMock())
    con_setting.set_controller("controller0", "slave-type")

    assert con_setting.setting.props.master == "controller0"
    assert con_setting.setting.props.slave_type == "slave-type"
