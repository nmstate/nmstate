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

import collections
import copy
import six
import time

from libnmstate import netinfo
from libnmstate import nm
from libnmstate import nmclient
from libnmstate import validator


def apply(desired_state):
    validator.verify(desired_state)

    interfaces_current_state = netinfo.interfaces()

    _apply_ifaces_state(desired_state['interfaces'], interfaces_current_state)

    # FIXME: Remove the sleep when the mainloop is added.
    # FIXME: Also revert to use assert_called_once_with() instead of
    # assert_called_with() in corresponding test cases
    time.sleep(1)

    interfaces_current_state = netinfo.interfaces()
    _apply_ifaces_state(desired_state['interfaces'], interfaces_current_state)
    time.sleep(1)
    # END FIXME


def _apply_ifaces_state(interfaces_desired_state, interfaces_current_state):
    # FIXME: Remove workaround when mainloop is integrated in the flow.
    nmclient.client(refresh=True)

    ifaces_desired_state = _index_by_name(interfaces_desired_state)
    ifaces_current_state = _index_by_name(interfaces_current_state)

    generate_ifaces_metadata(ifaces_desired_state, ifaces_current_state)

    _add_interfaces(ifaces_desired_state, ifaces_current_state)
    _edit_interfaces(ifaces_desired_state, ifaces_current_state)


def generate_ifaces_metadata(ifaces_desired_state, ifaces_current_state):
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
    _generate_link_aggr_metadata(ifaces_desired_state, ifaces_current_state)


def _generate_link_aggr_metadata(ifaces_desired_state, ifaces_current_state):
    """
    Given bonds slaves, add to the slave interface the master information.

    Possible scenarios for a given desired and current sate:
    - The desired state contains both the bonds and their slaves.
    - The desired state contains the bonds and partially (or not at all)
      the slaves. Some or all the slaves are in the current state.
    - Bond is in the current state and some of the slaves are in the desired
      state.
    """
    desired_bonds = [
        (ifname, ifstate)
        for ifname, ifstate in six.viewitems(ifaces_desired_state)
        if ifstate['type'] == 'bond'
    ]
    for bond_name, bond_state in desired_bonds:
        desired_link_aggr = bond_state.get('link-aggregation', {})
        desired_slaves = desired_link_aggr.get('slaves', [])
        for slave in desired_slaves:
            if slave in ifaces_desired_state:
                ifaces_desired_state[slave]['_master'] = bond_name
            elif slave in ifaces_current_state:
                ifaces_desired_state[slave] = {'_master': bond_name}

        desired_slaves = desired_link_aggr.get('slaves')
        current_bond_state = ifaces_current_state.get(bond_name)
        if desired_slaves and current_bond_state:
            current_slaves = current_bond_state['link-aggregation']['slaves']
            slaves2remove = (set(current_slaves) - set(desired_slaves))
            for slave in slaves2remove:
                if slave not in ifaces_desired_state:
                    ifaces_desired_state[slave] = {}

    current_bonds = (
        (ifname, ifstate)
        for ifname, ifstate in six.viewitems(ifaces_current_state)
        if ifstate['type'] == 'bond'
    )
    for bond_name, bond_state in current_bonds:
        current_link_aggr = bond_state.get('link-aggregation', {})
        current_slaves = current_link_aggr.get('slaves', [])
        for slave in current_slaves:
            if slave in ifaces_desired_state:
                iface_state = ifaces_desired_state.get(bond_name, {})
                if not _bond_slaves_defined(iface_state):
                    ifaces_desired_state[slave]['_master'] = bond_name


def _bond_slaves_defined(iface_state):
    link_aggr = iface_state.get('link-aggregation', {})
    if 'slaves' in link_aggr:
        return True
    return False


def _add_interfaces(ifaces_desired_state, ifaces_current_state):
    ifaces2add = [
        ifaces_desired_state[name] for name in
        six.viewkeys(ifaces_desired_state) - six.viewkeys(ifaces_current_state)
    ]

    validator.verify_interfaces_state(ifaces2add, ifaces_desired_state)

    ifaces_configs = nm.applier.prepare_new_ifaces_configuration(ifaces2add)
    nm.applier.create_new_ifaces(ifaces_configs)


def _edit_interfaces(ifaces_desired_state, ifaces_current_state):
    ifaces2edit = [
        _canonicalize_desired_state(ifaces_desired_state[name],
                                    ifaces_current_state[name])
        for name in
        six.viewkeys(ifaces_desired_state) & six.viewkeys(ifaces_current_state)
    ]

    validator.verify_interfaces_state(ifaces2edit, ifaces_desired_state)

    ifaces_configs = nm.applier.prepare_edited_ifaces_configuration(
        ifaces2edit)
    nm.applier.edit_existing_ifaces(ifaces_configs)

    nm.applier.set_ifaces_admin_state(ifaces2edit)


def _canonicalize_desired_state(iface_desired_state, iface_current_state):
    """
    Given the desired and current states, complete the desired state by merging
    the missing parts from the current state.
    """
    iface_current_state = copy.deepcopy(iface_current_state)
    return _dict_update(iface_current_state, iface_desired_state)


def _dict_update(origin_data, to_merge_data):
    """Recursevely performes a dict update (merge)"""

    for key, val in six.viewitems(to_merge_data):
        if isinstance(val, collections.Mapping):
            origin_data[key] = _dict_update(origin_data.get(key, {}), val)
        else:
            origin_data[key] = val

    return origin_data


def _index_by_name(ifaces_state):
    return {iface['name']: iface for iface in ifaces_state}
