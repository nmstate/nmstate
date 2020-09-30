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

import gi

gi.require_version("NM", "1.0")

# It is required to state the NM version before importing it
# But this break the flak8 rule: https://www.flake8rules.com/rules/E402.html
# Use NOQA: E402 to suppress it.
from gi.repository import NM  # NOQA: E402
from gi.repository import GLib  # NOQA: E402
from gi.repository import GObject  # NOQA: E402
from gi.repository import Gio  # NOQA: E402


# To suppress the "import not used" error
NM
GLib
GObject
Gio
