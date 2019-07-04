#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
import six

import libnmstate.nm.device as nm_device
import libnmstate.nm.nmclient as nmclient
import libnmstate.nm.wired as nm_wired
from libnmstate.base_iface import BaseInterface
from libnmstate.schema import Interface
from libnmstate.schema import Ethernet


class EthernetInterface(BaseInterface):
    NM_DEV_TYPES = (
        nmclient.NM.DeviceType.ETHERNET,
        nmclient.NM.DeviceType.VETH,
    )

    def __init__(self, iface_info=None, iface_name=None):
        super(EthernetInterface, self).__init__(
            iface_info=iface_info, iface_name=iface_name
        )
        if iface_name:
            iface_info = EthernetInterface._get(iface_name)
        ethernet = iface_info.get(Ethernet.CONFIG_SUBTREE, {})
        self.speed = ethernet.get(Ethernet.SPEED)
        self.duplex = ethernet.get(Ethernet.DUPLEX)
        self.auto_negotiation = ethernet.get(Ethernet.AUTO_NEGOTIATION)
        self.nm_setting_name = nmclient.NM.SETTING_WIRED_SETTING_NAME

    @staticmethod
    def _get(iface_name):
        dev = nm_device.get_device_by_name(iface_name)
        return nm_wired.get_info(dev)

    def dump(self):
        info = super(EthernetInterface, self).dump()
        if self.speed and self.speed != 0:
            info[Ethernet.CONFIG_SUBTREE] = {
                Ethernet.SPEED: self.speed,
                Ethernet.DUPLEX: self.duplex or 'unknown',
                Ethernet.AUTO_NEGOTIATION: self.auto_negotiation or 'unknown',
            }
        return info

    def generate_settings(self, base_con_profile=None):
        settings = super(EthernetInterface, self).generate_settings(
            base_con_profile
        )
        profile = base_con_profile.profile if base_con_profile else None
        settings.append(
            nm_wired.create_setting(
                self.dump(), base_con_profile=profile
            )
        )
        return settings
