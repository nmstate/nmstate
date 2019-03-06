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

from contextlib import contextmanager
from operator import itemgetter

import collections
import copy
import six

from libnmstate import iplib
from libnmstate import netinfo
from libnmstate import nm
from libnmstate import validator
from libnmstate.appliers import linux_bridge
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateLibnmError
from libnmstate.nm import nmclient
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Constants
from libnmstate.schema import InterfaceType


def apply(desired_state, verify_change=True):
    desired_state = copy.deepcopy(desired_state)
    validator.verify(desired_state)
    validator.verify_capabilities(desired_state, netinfo.capabilities())
    validator.verify_dhcp(desired_state)

    _apply_ifaces_state(desired_state[Constants.INTERFACES], verify_change)


def _apply_ifaces_state(interfaces_desired_state, verify_change):
    ifaces_desired_state = _index_by_name(interfaces_desired_state)
    ifaces_current_state = _index_by_name(netinfo.interfaces())

    ifaces_desired_state = sanitize_ethernet_state(ifaces_desired_state,
                                                   ifaces_current_state)
    ifaces_desired_state = sanitize_dhcp_state(ifaces_desired_state)
    generate_ifaces_metadata(ifaces_desired_state, ifaces_current_state)

    with _transaction():
        with _setup_providers():
            _add_interfaces(ifaces_desired_state, ifaces_current_state)
        with _setup_providers():
            ifaces_current_state = _index_by_name(netinfo.interfaces())
            _edit_interfaces(ifaces_desired_state, ifaces_current_state)
        if verify_change:
            _verify_change(ifaces_desired_state)


def _verify_change(ifaces_desired_state):
    ifaces_current_state = _index_by_name(netinfo.interfaces())
    ifaces_desired_state = _remove_absent_iface_entries(
        ifaces_desired_state)
    ifaces_desired_state = _remove_down_virt_iface_entries(
        ifaces_desired_state)
    ifaces_desired_state = remove_ifaces_metadata(ifaces_desired_state)

    assert_ifaces_state(ifaces_desired_state, ifaces_current_state)


@contextmanager
def _transaction():
    if nm.checkpoint.has_checkpoint_capability():
        checkpoint_ctx = nm.checkpoint.CheckPoint()
    else:
        checkpoint_ctx = _placeholder_ctx()

    with checkpoint_ctx:
        yield


@contextmanager
def _setup_providers():
    mainloop = nmclient.mainloop()
    yield
    success = mainloop.run(timeout=20)
    if not success:
        raise NmstateLibnmError(
            'Unexpected failure of libnm when running the mainloop: {}'.format(
                mainloop.error))


@contextmanager
def _placeholder_ctx():
    yield


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
    _generate_link_master_metadata(
        ifaces_desired_state,
        ifaces_current_state,
        master_type='bond',
        get_slaves_func=_get_bond_slaves_from_state,
        set_metadata_func=_set_common_slaves_metadata
    )
    _generate_link_master_metadata(
        ifaces_desired_state,
        ifaces_current_state,
        master_type='ovs-bridge',
        get_slaves_func=_get_ovs_slaves_from_state,
        set_metadata_func=_set_ovs_bridge_ports_metadata
    )
    _generate_link_master_metadata(
        ifaces_desired_state,
        ifaces_current_state,
        master_type='linux-bridge',
        get_slaves_func=linux_bridge.get_slaves_from_state,
        set_metadata_func=linux_bridge.set_bridge_ports_metadata
    )


def sanitize_ethernet_state(ifaces_desired_state, ifaces_current_state):
    """
    If auto-negotiation, speed and duplex settings are not provided,
    but exist in the current state, they need to be set to None
    to not override them with the values from the current settings
    since the current settings are read from the device state and not
    from the actual configuration.  This makes it possible to distiguish
    whether a user specified these values in the later configuration step.
    """
    for ifname, iface_state in six.viewitems(ifaces_desired_state):
        iface_current_state = ifaces_current_state.get(ifname, {})
        if iface_current_state.get('type') == 'ethernet':
            ethernet = iface_state.setdefault('ethernet', {})
            ethernet.setdefault('auto-negotiation', None)
            ethernet.setdefault('speed', None)
            ethernet.setdefault('duplex', None)
    return ifaces_desired_state


def sanitize_dhcp_state(ifaces_state):
    """
    If dynamic IP is enabled and IP address is missing, set an empty address
    list. This assures that the desired state is not complemented by the
    current state address values.
    If dynamic IP is disabled, all dynamic IP options should be removed.
    """
    for iface_state in six.viewvalues(ifaces_state):
        for family in ('ipv4', 'ipv6'):
            ip = iface_state.get(family, {})
            if ip.get('enabled') and (ip.get('dhcp') or ip.get('autoconf')):
                ip['address'] = []
            else:
                for dhcp_option in ('auto-routes',
                                    'auto-gateway',
                                    'auto-dns'):
                    ip.pop(dhcp_option, None)

    return ifaces_state


def remove_ifaces_metadata(ifaces_state):
    clean_ifaces_state = copy.deepcopy(ifaces_state)
    for iface_state in six.viewvalues(clean_ifaces_state):
        iface_state.pop('_master', None)
        iface_state.pop('_master_type', None)
        iface_state.pop('_brport_options', None)

    return clean_ifaces_state


def _get_bond_slaves_from_state(state, default=()):
    return state.get('link-aggregation', {}).get('slaves', default)


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


def _get_ovs_slaves_from_state(state, default=()):
    ports = state.get('bridge', {}).get('port')
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
                    ifaces_desired_state[slave] = {}

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


def _add_interfaces(ifaces_desired_state, ifaces_current_state):
    ifaces2add = [
        ifaces_desired_state[name] for name in
        six.viewkeys(ifaces_desired_state) - six.viewkeys(ifaces_current_state)
        if ifaces_desired_state[name].get('state') not in ('absent', 'down')
    ]

    validator.verify_interfaces_state(ifaces2add, ifaces_desired_state)

    ifaces2add += nm.applier.prepare_proxy_ifaces_desired_state(ifaces2add)
    ifaces_configs = nm.applier.prepare_new_ifaces_configuration(ifaces2add)
    nm.applier.create_new_ifaces(ifaces_configs)

    nm.applier.set_ifaces_admin_state(ifaces2add, con_profiles=ifaces_configs)


def _edit_interfaces(ifaces_desired_state, ifaces_current_state):
    ifaces2edit = [
        _canonicalize_desired_state(ifaces_desired_state[name],
                                    ifaces_current_state[name])
        for name in
        six.viewkeys(ifaces_desired_state) & six.viewkeys(ifaces_current_state)
    ]

    validator.verify_interfaces_state(ifaces2edit, ifaces_desired_state)

    iface2prepare = list(
        filter(lambda state: state.get('state') not in ('absent', 'down'),
               ifaces2edit)
    )
    proxy_ifaces = nm.applier.prepare_proxy_ifaces_desired_state(iface2prepare)
    ifaces_configs = nm.applier.prepare_edited_ifaces_configuration(
        iface2prepare + proxy_ifaces)
    nm.applier.edit_existing_ifaces(ifaces_configs)

    nm.applier.set_ifaces_admin_state(ifaces2edit + proxy_ifaces,
                                      con_profiles=ifaces_configs)


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


def assert_ifaces_state(ifaces_desired_state, ifaces_current_state):
    if not (set(ifaces_desired_state) <= set(ifaces_current_state)):
        raise NmstateVerificationError(
            format_desired_current_state_diff(ifaces_desired_state,
                                              ifaces_current_state))

    for ifname in ifaces_desired_state:
        iface_cstate = ifaces_current_state[ifname]
        iface_dstate = _canonicalize_desired_state(
            ifaces_desired_state[ifname], iface_cstate)

        iface_dstate, iface_cstate = _cleanup_iface_ethernet_state_sanitize(
            iface_dstate, iface_cstate)
        iface_dstate, iface_cstate = _sort_lag_slaves(
            iface_dstate, iface_cstate)
        iface_dstate, iface_cstate = _sort_bridge_ports(
            iface_dstate, iface_cstate)
        iface_dstate, iface_cstate = _canonicalize_ipv6_state(
            iface_dstate, iface_cstate)
        iface_dstate, iface_cstate = _remove_iface_ipv6_link_local_addr(
            iface_dstate, iface_cstate)
        iface_cstate = sanitize_dhcp_state({ifname: iface_cstate})[ifname]
        iface_dstate, iface_cstate = _sort_ip_addresses(
            iface_dstate, iface_cstate)

        if iface_dstate != iface_cstate:
            raise NmstateVerificationError(
                format_desired_current_state_diff(iface_dstate, iface_cstate))


def _cleanup_iface_ethernet_state_sanitize(desired_state, current_state):
    ethernet_desired_state = desired_state.get('ethernet')
    if ethernet_desired_state:
        ethernet_current_state = current_state.get('ethernet', {})
        for key in ('auto-negotiation', 'speed', 'duplex'):
            if ethernet_desired_state.get(key, None) is None:
                ethernet_desired_state.pop(key, None)
                ethernet_current_state.pop(key, None)
        if not ethernet_desired_state:
            desired_state.pop('ethernet', None)
            current_state.pop('ethernet', None)
    return desired_state, current_state


def _sort_lag_slaves(desired_state, current_state):
    for state in (desired_state, current_state):
        state.get('link-aggregation', {}).get('slaves', []).sort()
    return desired_state, current_state


def _sort_bridge_ports(desired_state, current_state):
    for state in (desired_state, current_state):
        state.get('bridge', {}).get('port', []).sort(key=itemgetter('name'))
    return desired_state, current_state


def _remove_absent_iface_entries(ifaces_desired_state):
    ifaces = {}
    for ifname, ifstate in six.viewitems(ifaces_desired_state):
        is_absent = ifstate.get('state') == 'absent'
        if not is_absent:
            ifaces[ifname] = ifstate
    return ifaces


def _remove_down_virt_iface_entries(ifaces_desired_state):
    ifaces = {}
    for ifname, ifstate in six.viewitems(ifaces_desired_state):
        is_virt_down = (
                ifstate.get('state') == 'down' and
                ifstate.get('type') in InterfaceType.VIRT_TYPES
        )
        if not is_virt_down:
            ifaces[ifname] = ifstate
    return ifaces


def _remove_iface_ipv6_link_local_addr(desired_state, current_state):
    for state in (desired_state, current_state):
        state['ipv6']['address'] = list(
            addr for addr in state['ipv6']['address']
            if not iplib.is_ipv6_link_local_addr(addr['ip'],
                                                 addr['prefix-length']))
    return desired_state, current_state


def _canonicalize_ipv6_state(desired_state, current_state):
    desired_state = _dict_update({'ipv6': {'enabled': False, 'address': []}},
                                 desired_state)
    current_state = _dict_update({'ipv6': {'enabled': False, 'address': []}},
                                 current_state)
    return desired_state, current_state


def _sort_ip_addresses(desired_state, current_state):
    for state in (desired_state, current_state):
        for family in ('ipv4', 'ipv6'):
            state.get(family, {}).get('address', []).sort(key=itemgetter('ip'))
    return desired_state, current_state
