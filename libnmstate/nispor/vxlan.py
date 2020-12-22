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
from libnmstate.schema import VXLAN

from .base_iface import NisporPluginBaseIface


class NisporPluginVxlanIface(NisporPluginBaseIface):
    @property
    def type(self):
        return InterfaceType.VXLAN

    def to_dict(self, config_only):
        info = super().to_dict(config_only)
        info[VXLAN.CONFIG_SUBTREE] = {
            VXLAN.ID: self._np_iface.vxlan_id,
            VXLAN.BASE_IFACE: self._np_iface.base_iface,
            VXLAN.REMOTE: self._np_iface.remote,
            VXLAN.DESTINATION_PORT: self._np_iface.dst_port,
        }

        return info
