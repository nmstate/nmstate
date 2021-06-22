#
# Copyright (c) 2018-2021 Red Hat, Inc.
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

from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from .common import NM


ZEROED_MAC = "00:00:00:00:00:00"


class WiredSetting:
    def __init__(self, state):
        self.mtu = state.get(Interface.MTU)
        self.mac = state.get(Interface.MAC)
        self.accept_all_mac_addrs = state.get(
            Interface.ACCEPT_ALL_MAC_ADDRESSES
        )

        ethernet = state.get(Ethernet.CONFIG_SUBTREE, {})
        self.speed = ethernet.get(Ethernet.SPEED)
        self.duplex = ethernet.get(Ethernet.DUPLEX)
        self.auto_negotiation = ethernet.get(Ethernet.AUTO_NEGOTIATION)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self is other or self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __bool__(self):
        return bool(
            self.mac
            or self.mtu
            or (self.accept_all_mac_addrs is not None)
            or self.speed
            or self.duplex
            or (self.auto_negotiation is not None)
        )

    def __key(self):
        return (
            self.mtu,
            self.mac,
            self.accept_all_mac_addrs,
            self.speed,
            self.duplex,
            self.auto_negotiation,
        )


def create_setting(iface, base_con_profile):
    setting = WiredSetting(iface.original_desire_dict)

    nm_wired_setting = None
    if base_con_profile:
        nm_wired_setting = base_con_profile.get_setting_wired()
        if nm_wired_setting:
            nm_wired_setting = nm_wired_setting.duplicate()

    # Don't create new wire setting when orignal desire state does not
    # required so.
    if not setting:
        return nm_wired_setting

    if not nm_wired_setting:
        nm_wired_setting = NM.SettingWired.new()

    if setting.mac:
        nm_wired_setting.props.cloned_mac_address = setting.mac

    if setting.mtu:
        nm_wired_setting.props.mtu = setting.mtu

    if setting.accept_all_mac_addrs is not None and hasattr(
        nm_wired_setting.props, "accept_all_mac_addresses"
    ):
        nm_wired_setting.props.accept_all_mac_addresses = (
            setting.accept_all_mac_addrs
        )

    if setting.auto_negotiation is True:
        nm_wired_setting.props.auto_negotiate = True
        nm_wired_setting.props.speed = 0
        nm_wired_setting.props.duplex = None
    elif setting.auto_negotiation is False:
        nm_wired_setting.props.auto_negotiate = False
        if iface.speed is not None:
            nm_wired_setting.props.speed = iface.speed
        if iface.duplex in (Ethernet.FULL_DUPLEX, Ethernet.HALF_DUPLEX):
            nm_wired_setting.props.duplex = iface.duplex

    return nm_wired_setting
