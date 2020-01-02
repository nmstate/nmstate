#
# Copyright (c) 2018-2020 Red Hat, Inc.
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

from libnmstate.ethtool import minimal_ethtool
from libnmstate.nm import nmclient
from libnmstate.nm import sriov
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface


ZEROED_MAC = "00:00:00:00:00:00"


class WiredSetting:
    def __init__(self, state):
        self.mtu = state.get(Interface.MTU)
        self.mac = state.get(Interface.MAC)

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
            or self.speed
            or self.duplex
            or (self.auto_negotiation is not None)
        )

    def __key(self):
        return (
            self.mtu,
            self.mac,
            self.speed,
            self.duplex,
            self.auto_negotiation,
        )


def create_setting(iface_state, base_con_profile):
    setting = WiredSetting(iface_state)

    nm_wired_setting = None
    if base_con_profile:
        nm_wired_setting = base_con_profile.get_setting_wired()
        if nm_wired_setting:
            nm_wired_setting = nm_wired_setting.duplicate()

    if not setting:
        return nm_wired_setting

    if not nm_wired_setting:
        nm_wired_setting = nmclient.NM.SettingWired.new()

    if setting.mac:
        nm_wired_setting.props.cloned_mac_address = setting.mac

    if setting.mtu:
        nm_wired_setting.props.mtu = setting.mtu

    if setting.auto_negotiation:
        nm_wired_setting.props.auto_negotiate = True
        if not setting.speed and not setting.duplex:
            nm_wired_setting.props.speed = 0
            nm_wired_setting.props.duplex = None

        elif not setting.speed:
            ethtool_results = minimal_ethtool(str(iface_state[Interface.NAME]))
            setting.speed = ethtool_results[Ethernet.SPEED]
        elif not setting.duplex:
            ethtool_results = minimal_ethtool(str(iface_state[Interface.NAME]))
            setting.duplex = ethtool_results[Ethernet.DUPLEX]

    elif setting.auto_negotiation is False:
        nm_wired_setting.props.auto_negotiate = False
        ethtool_results = minimal_ethtool(str(iface_state[Interface.NAME]))
        if not setting.speed:
            setting.speed = ethtool_results[Ethernet.SPEED]
        if not setting.duplex:
            setting.duplex = ethtool_results[Ethernet.DUPLEX]

    if setting.speed:
        nm_wired_setting.props.speed = setting.speed

    if setting.duplex in [Ethernet.HALF_DUPLEX, Ethernet.FULL_DUPLEX]:
        nm_wired_setting.props.duplex = setting.duplex

    return nm_wired_setting


def get_info(device):
    """
    Provides the current active values for a device
    """
    info = {}

    iface = device.get_iface()
    try:
        info[Interface.MTU] = int(device.get_mtu())
    except AttributeError:
        pass

    mac = device.get_hw_address()
    if not mac:
        mac = _get_mac_address_from_sysfs(iface)

    # A device may not have a MAC or it may not yet be "realized" (zeroed mac).
    if mac and mac != ZEROED_MAC:
        info[Interface.MAC] = mac

    if device.get_device_type() == nmclient.NM.DeviceType.ETHERNET:
        ethernet = _get_ethernet_info(device, iface)
        if ethernet:
            info[Ethernet.CONFIG_SUBTREE] = ethernet

    return info


def _get_mac_address_from_sysfs(ifname):
    """
    Fetch the mac address of an interface from sysfs.
    This is a workaround for https://bugzilla.redhat.com/1786937.
    """
    mac = None
    sysfs_path = f"/sys/class/net/{ifname}/address"
    try:
        with open(sysfs_path) as f:
            mac = f.read().rstrip("\n")
    except FileNotFoundError:
        pass
    return mac


def _get_ethernet_info(device, iface):
    ethernet = {}
    try:
        speed = int(device.get_speed())
        if speed > 0:
            ethernet[Ethernet.SPEED] = speed
        else:
            return None
    except AttributeError:
        return None

    ethtool_results = minimal_ethtool(iface)
    auto_setting = ethtool_results[Ethernet.AUTO_NEGOTIATION]
    if auto_setting is True:
        ethernet[Ethernet.AUTO_NEGOTIATION] = True
    elif auto_setting is False:
        ethernet[Ethernet.AUTO_NEGOTIATION] = False
    else:
        return None

    duplex_setting = ethtool_results[Ethernet.DUPLEX]
    if duplex_setting in [Ethernet.HALF_DUPLEX, Ethernet.FULL_DUPLEX]:
        ethernet[Ethernet.DUPLEX] = duplex_setting
    else:
        return None

    sriov_info = sriov.get_info(device)
    if sriov_info:
        ethernet.update(sriov_info)

    return ethernet
