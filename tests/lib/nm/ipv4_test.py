#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from lib.compat import mock

from libnmstate import nm


@mock.patch.object(nm.ipv4.nmclient, 'NM')
def test_create_setting(NM_mock):
    ipv4_setting = nm.ipv4.create_setting()

    assert ipv4_setting == NM_mock.SettingIP4Config.new.return_value
    assert (ipv4_setting.props.method ==
            NM_mock.SETTING_IP4_CONFIG_METHOD_DISABLED)
