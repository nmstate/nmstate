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

from . import bond
from . import connection
from . import device
from . import ipv4
from . import ipv6
from . import ovs
from . import translator


class UnsupportedIfaceStateError(Exception):
    pass


class UnsupportedIfaceTypeError(Exception):
    pass


def create_new_ifaces(con_profiles):
    for connection_profile in con_profiles:
        connection.add_profile(connection_profile, save_to_disk=True)


def prepare_new_ifaces_configuration(ifaces_desired_state):
    return [
        _build_connection_profile(iface_desired_state)
        for iface_desired_state in ifaces_desired_state
    ]


def edit_existing_ifaces(con_profiles):
    for connection_profile in con_profiles:
        devname = connection_profile.get_interface_name()
        nmdev = device.get_device_by_name(devname)
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.get_device_connection(nmdev)
        if cur_con_profile:
            connection.commit_profile(connection_profile)
        else:
            # Missing connection, attempting to create a new one.
            connection.add_profile(connection_profile, save_to_disk=True)


def prepare_edited_ifaces_configuration(ifaces_desired_state):
    con_profiles = []

    for iface_desired_state in ifaces_desired_state:
        nmdev = device.get_device_by_name(iface_desired_state['name'])
        cur_con_profile = None
        if nmdev:
            cur_con_profile = connection.get_device_connection(nmdev)
        new_con_profile = _build_connection_profile(
            iface_desired_state, base_con_profile=cur_con_profile)
        if cur_con_profile:
            connection.update_profile(cur_con_profile, new_con_profile)
            con_profiles.append(cur_con_profile)
        else:
            # Missing connection, attempting to create a new one.
            con_profiles.append(new_con_profile)

    return con_profiles


def set_ifaces_admin_state(ifaces_desired_state):
    for iface_desired_state in ifaces_desired_state:
        if iface_desired_state['state'] == 'up':
            _set_dev_state(iface_desired_state, device.activate)
        elif iface_desired_state['state'] == 'down':
            _set_dev_state(iface_desired_state, device.delete)
        elif iface_desired_state['state'] == 'absent':
            _set_dev_state(iface_desired_state, device.delete)
        else:
            raise UnsupportedIfaceStateError(iface_desired_state)


def _set_dev_state(iface_state, func_action):
    nmdev = device.get_device_by_name(iface_state['name'])
    if nmdev:
        devs = [nmdev]
        iface_type = iface_state['type']
        if iface_type == ovs.BRIDGE_TYPE:
            devs += _get_ovs_bridge_port_devices(iface_state)
        elif iface_type == bond.BOND_TYPE:
            devs += bond.get_slaves(nmdev)
        for dev in devs:
            func_action(dev)


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

    # TODO: Support ovs-interface type on setup
    if iface_type == ovs.INTERNAL_INTERFACE_TYPE:
        raise UnsupportedIfaceTypeError(iface_type,
                                        iface_desired_state['name'])

    settings = [
        ipv4.create_setting(iface_desired_state.get('ipv4')),
        ipv6.create_setting(),
    ]
    if base_con_profile:
        con_setting = connection.duplicate_settings(base_con_profile)
    else:
        con_setting = connection.create_setting(
            con_name=iface_desired_state['name'],
            iface_name=iface_desired_state['name'],
            iface_type=iface_type,
        )
    master = iface_desired_state.get('_master')
    master_type = iface_desired_state.get('_master_type')
    connection.set_master_setting(con_setting, master, master_type)
    settings.append(con_setting)

    bond_opts = translator.Api2Nm.get_bond_options(iface_desired_state)
    if bond_opts:
        settings.append(bond.create_setting(bond_opts))
    elif iface_type == ovs.BRIDGE_TYPE:
        ovs_bridge_options = ovs.translate_bridge_options(iface_desired_state)
        if ovs_bridge_options:
            settings.append(ovs.create_bridge_setting(ovs_bridge_options))
    elif iface_type == ovs.PORT_TYPE:
        ovs_port_options = iface_desired_state.get('options')
        settings.append(ovs.create_port_setting(ovs_port_options))

    return connection.create_profile(settings)
