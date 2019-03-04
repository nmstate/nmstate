#
# Copyright 2018-2019 Red Hat, Inc.
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

from libnmstate.schema import LinuxBridge as LB
from libnmstate.error import NmstateValueError

from . import bond
from . import bridge
from . import connection
from . import device
from . import ipv4
from . import ipv6
from . import nmclient
from . import ovs
from . import translator
from . import user
from . import vlan
from . import wired


def create_new_ifaces(con_profiles):
    for connection_profile in con_profiles:
        connection_profile.add(save_to_disk=True)


def prepare_new_ifaces_configuration(ifaces_desired_state):
    return [
        _build_connection_profile(iface_desired_state)
        for iface_desired_state in ifaces_desired_state
    ]


def edit_existing_ifaces(con_profiles):
    for connection_profile in con_profiles:
        devname = connection_profile.devname
        nmdev = device.get_device_by_name(devname)
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.ConnectionProfile()
            cur_con_profile.import_by_device(nmdev)
        if cur_con_profile and cur_con_profile.profile:
            connection_profile.commit(nmdev=nmdev)
        else:
            # Missing connection, attempting to create a new one.
            connection_profile.add(save_to_disk=True)


def prepare_edited_ifaces_configuration(ifaces_desired_state):
    con_profiles = []

    for iface_desired_state in ifaces_desired_state:
        nmdev = device.get_device_by_name(iface_desired_state['name'])
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.ConnectionProfile()
            cur_con_profile.import_by_device(nmdev)
        new_con_profile = _build_connection_profile(
            iface_desired_state, base_con_profile=cur_con_profile)
        if not new_con_profile.devname:
            set_conn = new_con_profile.profile.get_setting_connection()
            set_conn.props.interface_name = iface_desired_state['name']
        if cur_con_profile and cur_con_profile.profile:
            cur_con_profile.update(new_con_profile)
            con_profiles.append(cur_con_profile)
        else:
            # Missing connection, attempting to create a new one.
            con_profiles.append(new_con_profile)

    return con_profiles


def set_ifaces_admin_state(ifaces_desired_state, con_profiles=()):
    """
    Control interface admin state by activating, deactivating and deleting
    devices connection profiles.

    The `absent` state results in deactivating the device and deleting
    the connection profile.
    FIXME: The `down` state is currently handled in the same way.

    For new virtual devices, the `up` state is handled by activating the
    new connection profile. For existing devices, the device is activated,
    leaving it to choose the correct profile.

    In order to activate correctly the interfaces, the order is significant:
    - New interfaces (virtual interfaces, but not OVS ones).
    - Master interfaces.
    - OVS ports.
    - OVS internal.
    - All the rest.
    """
    new_ifaces = _get_new_ifaces(con_profiles)
    new_ifaces_to_activate = set()
    new_ovs_interface_to_activate = set()
    new_ovs_port_to_activate = set()
    master_ifaces_to_activate = set()
    devs_actions = {}

    for iface_desired_state in ifaces_desired_state:
        nmdev = device.get_device_by_name(iface_desired_state['name'])
        if not nmdev:
            ifname = iface_desired_state['name']
            if ifname in new_ifaces and iface_desired_state['state'] == 'up':
                if iface_desired_state['type'] == ovs.INTERNAL_INTERFACE_TYPE:
                    new_ovs_interface_to_activate.add(ifname)
                elif iface_desired_state['type'] == ovs.PORT_TYPE:
                    new_ovs_port_to_activate.add(ifname)
                else:
                    new_ifaces_to_activate.add(ifname)
        else:
            if iface_desired_state['state'] == 'up':
                master_iface_types = ovs.BRIDGE_TYPE, bond.BOND_TYPE, LB.TYPE
                if iface_desired_state['type'] in master_iface_types:
                    master_ifaces_to_activate.add(nmdev)
                else:
                    devs_actions[nmdev] = (device.activate,)
            elif iface_desired_state['state'] in ('down', 'absent'):
                nmdevs = _get_affected_devices(iface_desired_state)
                for nmdev in nmdevs:
                    devs_actions[nmdev] = [device.deactivate, device.delete]
                    if nmdev.get_device_type() in (
                            nmclient.NM.DeviceType.OVS_BRIDGE,
                            nmclient.NM.DeviceType.OVS_PORT,
                            nmclient.NM.DeviceType.OVS_INTERFACE):
                        devs_actions[nmdev].append(device.delete_device)
            else:
                raise NmstateValueError(
                    'Invalid state {} for interface {}'.format(
                        iface_desired_state['state'],
                        iface_desired_state['name']))

    for ifname in new_ifaces_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for dev in master_ifaces_to_activate:
        device.activate(dev)

    for ifname in new_ovs_port_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for ifname in new_ovs_interface_to_activate:
        device.activate(dev=None, connection_id=ifname)

    for dev, actions in six.viewitems(devs_actions):
        for action in actions:
            action(dev)


def _get_new_ifaces(con_profiles):
    ifaces_without_device = set()
    for con_profile in con_profiles:
        ifname = con_profile.devname
        nmdev = device.get_device_by_name(ifname)
        if not nmdev:
            ifaces_without_device.add(ifname)
    return ifaces_without_device


def _get_affected_devices(iface_state):
    nmdev = device.get_device_by_name(iface_state['name'])
    devs = []
    if nmdev:
        devs += [nmdev]
        iface_type = iface_state['type']
        if iface_type == ovs.BRIDGE_TYPE:
            devs += _get_ovs_bridge_port_devices(iface_state)
        elif iface_type == LB.TYPE:
            devs += bridge.get_slaves(nmdev)
        elif iface_type == bond.BOND_TYPE:
            devs += bond.get_slaves(nmdev)
    return devs


def _get_ovs_bridge_port_devices(iface_state):
    """
    Report a list of all ovs ports and interfaces that are connected to the
    OVS bridge.
    Note: Ports must be activated before the ifaces (NM limitation).
    """
    ifaces = [p['name'] for p in iface_state.get('bridge', {}).get('port', [])]
    ports = [ovs.PORT_PROFILE_PREFIX + iface for iface in ifaces]
    devnames = ports + ifaces
    nmdevs = []
    for devname in devnames:
        dev = device.get_device_by_name(devname)
        if dev:
            nmdevs.append(dev)
    return nmdevs


def prepare_proxy_ifaces_desired_state(ifaces_desired_state):
    """
    Prepare the state of the "proxy" interfaces. These are interfaces that
    exist as NM entities/profiles, but are invisible to the API.
    These proxy interfaces state is created as a side effect of other ifaces
    definition.
    Note: This function modifies the ifaces_desired_state content in addition
    to returning a new set of states for the proxy interfaces.

    In OVS case, the port profile is the proxy, it is not part of the public
    state of the system, but internal to the NM provider.
    """
    new_ifaces_desired_state = []
    for iface_desired_state in ifaces_desired_state:
        master_type = iface_desired_state.get('_master_type')
        if master_type != ovs.BRIDGE_TYPE:
            continue
        port_options_metadata = iface_desired_state.get('_brport_options')
        if port_options_metadata is None:
            continue
        port_options = ovs.translate_port_options(port_options_metadata)
        port_iface_desired_state = _create_ovs_port_iface_desired_state(
            iface_desired_state, port_options)
        new_ifaces_desired_state.append(port_iface_desired_state)
        # The "visible" slave/interface needs to point to the port profile
        iface_desired_state['_master'] = port_iface_desired_state['name']
        iface_desired_state['_master_type'] = ovs.PORT_TYPE
    return new_ifaces_desired_state


def _create_ovs_port_iface_desired_state(iface_desired_state, port_options):
    return {
        'name': ovs.PORT_PROFILE_PREFIX + iface_desired_state['name'],
        'type': ovs.PORT_TYPE,
        'state': iface_desired_state['state'],
        '_master': iface_desired_state['_master'],
        '_master_type': iface_desired_state['_master_type'],
        'options': port_options,
    }


def _build_connection_profile(iface_desired_state, base_con_profile=None):
    iface_type = translator.Api2Nm.get_iface_type(iface_desired_state['type'])

    base_profile = base_con_profile.profile if base_con_profile else None

    settings = [
        ipv4.create_setting(iface_desired_state.get('ipv4'), base_profile),
        ipv6.create_setting(iface_desired_state.get('ipv6'), base_profile),
    ]

    con_setting = connection.ConnectionSetting()
    if base_profile:
        con_setting.import_by_profile(base_con_profile)
    else:
        con_setting.create(
            con_name=iface_desired_state['name'],
            iface_name=iface_desired_state['name'],
            iface_type=iface_type,
        )
    master = iface_desired_state.get('_master')
    _translate_master_type(iface_desired_state)
    master_type = iface_desired_state.get('_master_type')
    con_setting.set_master(master, master_type)
    settings.append(con_setting.setting)

    wired_setting = wired.create_setting(iface_desired_state, base_profile)
    if wired_setting:
        settings.append(wired_setting)

    user_setting = user.create_setting(iface_desired_state, base_profile)
    if user_setting:
        settings.append(user_setting)

    bond_opts = translator.Api2Nm.get_bond_options(iface_desired_state)
    if bond_opts:
        settings.append(bond.create_setting(bond_opts))
    elif iface_type == bridge.BRIDGE_TYPE:
        bridge_options = iface_desired_state.get('bridge', {}).get('options')
        if bridge_options:
            linux_bridge_setting = bridge.create_setting(bridge_options,
                                                         base_profile)
            settings.append(linux_bridge_setting)
    elif iface_type == ovs.BRIDGE_TYPE:
        ovs_bridge_options = ovs.translate_bridge_options(iface_desired_state)
        if ovs_bridge_options:
            settings.append(ovs.create_bridge_setting(ovs_bridge_options))
    elif iface_type == ovs.PORT_TYPE:
        ovs_port_options = iface_desired_state.get('options')
        settings.append(ovs.create_port_setting(ovs_port_options))
    elif iface_type == ovs.INTERNAL_INTERFACE_TYPE:
        settings.append(ovs.create_interface_setting())

    bridge_port_options = iface_desired_state.get('_brport_options')
    if bridge_port_options and master_type == bridge.BRIDGE_TYPE:
        settings.append(
            bridge.create_port_setting(bridge_port_options, base_profile)
        )

    vlan_setting = vlan.create_setting(iface_desired_state, base_profile)
    if vlan_setting:
        settings.append(vlan_setting)

    new_profile = connection.ConnectionProfile()
    new_profile.create(settings)
    return new_profile


def _translate_master_type(iface_desired_state):
    """
    Translates the master type metadata names to their equivalent
    NM type names.
    """
    master_type = iface_desired_state.get('_master_type')
    if master_type == LB.TYPE:
        iface_desired_state['_master_type'] = bridge.BRIDGE_TYPE
