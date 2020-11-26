#
# Copyright (c) 2021 Red Hat, Inc.
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
from libnmstate.schema import Veth

from .base_iface import NisporPluginBaseIface


class NisporPluginVethIface(NisporPluginBaseIface):
    @property
    def type(self):
        return InterfaceType.VETH

    def to_dict(self, config_only):
        info = super().to_dict(config_only)
        info[Veth.CONFIG_SUBTREE] = {
            Veth.PEER: self._np_iface.peer,
        }
        return info
