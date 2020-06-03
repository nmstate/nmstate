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

from libnmstate.schema import InterfaceType

from libnmstate.ifaces.dummy import DummyIface

from ..testlib.ifacelib import gen_foo_iface_info


class TestDummyIface:
    def _gen_iface_info(self):
        return gen_foo_iface_info(iface_type=InterfaceType.DUMMY)

    def test_team_is_virtual(self):
        assert DummyIface(self._gen_iface_info()).is_virtual
