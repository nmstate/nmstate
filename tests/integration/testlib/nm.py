#
# Copyright (c) 2019 Red Hat, Inc.
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

import gi  # pylint: disable=import-error

gi.require_version('NM', '1.0')  # NOQA: F402
from gi.repository import NM  # pylint: disable=no-name-in-module


def nm_version(major, minor, micro):
    return major * 10000 + minor * 100 + micro


def current_nm_version():
    return nm_version(NM.MAJOR_VERSION, NM.MINOR_VERSION, NM.MICRO_VERSION)
