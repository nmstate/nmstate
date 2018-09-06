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


def create_setting(iface_state, base_con_profile):
    mtu = iface_state.get('mtu')

    ethernet = iface_state.get('ethernet', {})
    speed = ethernet.get('speed')
    duplex = ethernet.get('duplex')
    auto_negotiation = ethernet.get('auto-negotiation')

    if not (mtu or speed or duplex or (auto_negotiation is not None)):
        return None

    wired_setting = None
    if base_con_profile:
        wired_setting = base_con_profile.get_setting_wired()
        if wired_setting:
            wired_setting = wired_setting.duplicate()

    if not wired_setting:
        wired_setting = nmclient.NM.SettingWired.new()

    if mtu:
        wired_setting.props.mtu = mtu

    if auto_negotiation:
        wired_setting.props.auto_negotiate = True
        if not speed:
            wired_setting.props.speed = 0

        if not duplex:
            wired_setting.props.duplex = None

    elif auto_negotiation is False:
        wired_setting.props.auto_negotiate = False

    if speed:
        wired_setting.props.speed = speed

    if duplex:
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

    ethernet = {}
    try:
        speed = int(device.get_speed())
        if speed > 0:
            ethernet['speed'] = speed
    except AttributeError:
        pass

    ethtool_results = minimal_ethtool(iface)
    auto_setting = ethtool_results['auto-negotiation']

    if auto_setting is True:
        ethernet['auto-negotiation'] = True
    elif auto_setting is False:
        ethernet['auto-negotiation'] = False

    duplex_setting = ethtool_results['duplex']
    if duplex_setting != 'unknown':
        ethernet['duplex'] = duplex_setting

    if ethernet:
        info['ethernet'] = ethernet

    return info
