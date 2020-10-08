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

from libnmstate.schema import MacVtap

from .macvlan import MacVlanIface


class MacVtapIface(MacVlanIface):
    @property
    def parent(self):
        return self.config_subtree.get(MacVtap.BASE_IFACE)

    @property
    def config_subtree(self):
        return self.raw.get(MacVtap.CONFIG_SUBTREE, {})
