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
from __future__ import absolute_import

try:
    import gi                           # pylint: disable=import-error
    gi.require_version('NM', '1.0')     # NOQA: F402
    from gi.repository import NM        # pylint: disable=import-error
except ImportError:
    # Allow the error to pass in case we are running in a unit test context
    g = None
    NM = None


_nmclient = None


def client():
    global _nmclient
    if _nmclient is None:
        _nmclient = NM.Client.new(None)
    return _nmclient
