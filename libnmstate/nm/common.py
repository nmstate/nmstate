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

from distutils.version import StrictVersion

import gi

try:
    gi.require_version("NM", "1.0")  # NOQA: F402
    from gi.repository import NM  # pylint: disable=no-name-in-module
except ValueError:
    NM = None

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio


def nm_version_bigger_or_equal_to(version):
    return StrictVersion(
        f"{NM.MAJOR_VERSION}.{NM.MINOR_VERSION}.{NM.MICRO_VERSION}"
    ) >= StrictVersion(version)


# To suppress the "import not used" error
NM
GLib
GObject
Gio
