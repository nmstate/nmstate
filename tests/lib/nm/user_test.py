#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import pytest

from lib.compat import mock

from libnmstate import nm


@pytest.fixture
def NM_mock():
    with mock.patch.object(nm.user.nmclient, 'NM') as m:
        yield m


def test_create_no_setting(NM_mock):
    setting = nm.user.create_setting({}, None)
    assert setting is None


def test_create_setting_duplicate(NM_mock):
    base_profile = mock.MagicMock()

    setting = nm.user.create_setting({'description': 'test_interface'},
                                     base_profile)
    base_profile.get_setting_by_name.assert_called_with(
        NM_mock.SETTING_USER_SETTING_NAME)
    assert setting == \
        base_profile.get_setting_by_name.return_value.duplicate.return_value


def test_create_setting_description(NM_mock):
    setting = nm.user.create_setting({'description': 'test_interface'}, None)
    assert setting == NM_mock.SettingUser.new.return_value
    setting.set_data.assert_called_with('nmstate.interface.description',
                                        'test_interface')
