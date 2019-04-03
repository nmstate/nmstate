#
# Copyright 2018 Red Hat, Inc.
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

from libnmstate.ethtool import minimal_ethtool
from libnmstate.nm import nmclient
from libnmstate.schema import Interface


ZEROED_MAC = '00:00:00:00:00:00'


def create_setting(iface_state, base_con_profile):
    mtu = iface_state.get('mtu')
    mac = iface_state.get(Interface.MAC)

    ethernet = iface_state.get('ethernet', {})
    speed = ethernet.get('speed')
    duplex = ethernet.get('duplex')
    auto_negotiation = ethernet.get('auto-negotiation')

    if not (mac or mtu or speed or duplex or (auto_negotiation is not None)):
        return None

    wired_setting = None
    if base_con_profile:
        wired_setting = base_con_profile.get_setting_wired()
        if wired_setting:
            wired_setting = wired_setting.duplicate()

    if not wired_setting:
        wired_setting = nmclient.NM.SettingWired.new()

    if mac:
        wired_setting.props.cloned_mac_address = mac

    if mtu:
        wired_setting.props.mtu = mtu

    if auto_negotiation:
        wired_setting.props.auto_negotiate = True
        if not speed and not duplex:
            wired_setting.props.speed = 0
            wired_setting.props.duplex = None

        elif not speed:
            ethtool_results = minimal_ethtool(str(iface_state['name']))
            speed = ethtool_results['speed']
        elif not duplex:
            ethtool_results = minimal_ethtool(str(iface_state['name']))
            duplex = ethtool_results['duplex']

    elif auto_negotiation is False:
        wired_setting.props.auto_negotiate = False
        ethtool_results = minimal_ethtool(str(iface_state['name']))
        if not speed:
            speed = ethtool_results['speed']
        if not duplex:
            duplex = ethtool_results['duplex']

    if speed:
        wired_setting.props.speed = speed

    if duplex in ['half', 'full']:
        wired_setting.props.duplex = duplex

    return wired_setting


def get_info(device):
    """
    Provides the current active values for a device
    """
    info = {}

    iface = device.get_iface()
    try:
        info['mtu'] = int(device.get_mtu())
    except AttributeError:
        pass

    mac = device.get_hw_address()
    # A device may not have a MAC or it may not yet be "realized" (zeroed mac).
    if mac and mac != ZEROED_MAC:
        info[Interface.MAC] = mac

    if device.get_device_type() == nmclient.NM.DeviceType.ETHERNET:
        ethernet = _get_ethernet_info(device, iface)
        if ethernet:
            info['ethernet'] = ethernet

    return info


def _get_ethernet_info(device, iface):
    ethernet = {}
    try:
        speed = int(device.get_speed())
        if speed > 0:
            ethernet['speed'] = speed
        else:
            return None
    except AttributeError:
        return None

    ethtool_results = minimal_ethtool(iface)
    auto_setting = ethtool_results['auto-negotiation']
    if auto_setting is True:
        ethernet['auto-negotiation'] = True
    elif auto_setting is False:
        ethernet['auto-negotiation'] = False
    else:
        return None

    duplex_setting = ethtool_results['duplex']
    if duplex_setting in ['half', 'full']:
        ethernet['duplex'] = duplex_setting
    else:
        return None
    return ethernet
