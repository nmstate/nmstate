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

from libnmstate.appliers import linux_bridge


def generate_ifaces_metadata(desired_state, current_state):
    """
    The described desired state for each interface may include references to
    other interfaces. As the provider handles the interface setting in an
    isolated manner, it is sometime necessary to specify a property on an
    interface based on a property from a different interface.
    An exmaple of this, is the bond slaves property, which should mark each
    slave with the setting of it being a slave.

    For such relationships between interfaces or some other potential inputs,
    metadata is generated on interfaces, usable by the provider when
    configuring the interface.
    """
    _generate_link_master_metadata(
        desired_state.interfaces,
        current_state.interfaces,
        master_type='bond',
        get_slaves_func=_get_bond_slaves_from_state,
        set_metadata_func=_set_common_slaves_metadata
    )
    _generate_link_master_metadata(
        desired_state.interfaces,
        current_state.interfaces,
        master_type='ovs-bridge',
        get_slaves_func=_get_ovs_slaves_from_state,
        set_metadata_func=_set_ovs_bridge_ports_metadata
    )
    _generate_link_master_metadata(
        desired_state.interfaces,
        current_state.interfaces,
        master_type='linux-bridge',
        get_slaves_func=linux_bridge.get_slaves_from_state,
        set_metadata_func=linux_bridge.set_bridge_ports_metadata
    )


def remove_ifaces_metadata(ifaces_state):
    for iface_state in six.viewvalues(ifaces_state.interfaces):
        iface_state.pop('_master', None)
        iface_state.pop('_master_type', None)
        iface_state.pop('_brport_options', None)


def _get_bond_slaves_from_state(iface_state, default=()):
    return iface_state.get('link-aggregation', {}).get('slaves', default)


def _set_ovs_bridge_ports_metadata(master_state, slave_state):
    _set_common_slaves_metadata(master_state, slave_state)

    ports = master_state.get('bridge', {}).get('port', [])
    port = next(
        six.moves.filter(lambda n: n['name'] == slave_state['name'], ports),
        {}
    )
    slave_state['_brport_options'] = port


def _set_common_slaves_metadata(master_state, slave_state):
    slave_state['_master'] = master_state['name']
    slave_state['_master_type'] = master_state['type']


def _get_ovs_slaves_from_state(iface_state, default=()):
    ports = iface_state.get('bridge', {}).get('port')
    if ports is None:
        return default
    return [p['name'] for p in ports]


def _generate_link_master_metadata(ifaces_desired_state,
                                   ifaces_current_state,
                                   master_type,
                                   get_slaves_func,
                                   set_metadata_func):
    """
    Given master's slaves, add to the slave interface the master information.

    Possible scenarios for a given desired and current sate:
    - The desired state contains both the masters and their slaves.
    - The desired state contains the masters and partially (or not at all)
      the slaves. Some or all the slaves are in the current state.
    - Master is in the current state and some of the slaves are in the desired
      state.
    """
    desired_masters = [
        (ifname, ifstate)
        for ifname, ifstate in six.viewitems(ifaces_desired_state)
        if ifstate.get('type') == master_type
    ]
    for master_name, master_state in desired_masters:
        desired_slaves = get_slaves_func(master_state)
        for slave in desired_slaves:
            if slave in ifaces_desired_state:
                set_metadata_func(master_state, ifaces_desired_state[slave])
            elif slave in ifaces_current_state:
                ifaces_desired_state[slave] = {'name': slave,
                                               'state': master_state['state']}
                set_metadata_func(master_state, ifaces_desired_state[slave])

        desired_slaves = get_slaves_func(master_state)
        current_master_state = ifaces_current_state.get(master_name)
        if desired_slaves and current_master_state:
            current_slaves = get_slaves_func(current_master_state)
            slaves2remove = (set(current_slaves) - set(desired_slaves))
            for slave in slaves2remove:
                if slave not in ifaces_desired_state:
                    ifaces_desired_state[slave] = {'name': slave}

    current_masters = (
        (ifname, ifstate)
        for ifname, ifstate in six.viewitems(ifaces_current_state)
        if ifstate.get('type') == master_type
    )
    for master_name, master_state in current_masters:
        current_slaves = get_slaves_func(master_state)
        for slave in current_slaves:
            if slave in ifaces_desired_state:
                iface_state = ifaces_desired_state.get(master_name, {})
                master_has_no_slaves_specified_in_desired = (
                    get_slaves_func(iface_state, None) is None)
                slave_has_no_master_specified_in_desired = (
                    ifaces_desired_state[slave].get('_master') is None)
                if (slave_has_no_master_specified_in_desired and
                        master_has_no_slaves_specified_in_desired):
                    set_metadata_func(
                        master_state, ifaces_desired_state[slave])
