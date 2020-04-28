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

from .nmstate import show_with_plugin
from .nmstate import plugin_context


def show(*, include_status_data=False):
    """
    Reports configuration and status data on the system.
    Configuration data is the set of writable data which can change the system
    state.
    Status data is the additional data which is not configuration data,
    including read-only and statistics information.
    When include_status_data is set, both are reported, otherwise only the
    configuration data is reported.
    """
    with plugin_context() as plugin:
        return show_with_plugin(plugin, include_status_data)
