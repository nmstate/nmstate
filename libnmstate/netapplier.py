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
from libnmstate import metadata
from libnmstate import netinfo
from libnmstate import nm
from libnmstate import state
from libnmstate import validator
from libnmstate.error import NmstateVerificationError
from libnmstate.error import NmstateLibnmError
from libnmstate.nm import nmclient
from libnmstate.prettystate import format_desired_current_state_diff
from libnmstate.schema import Constants


def apply(desired_state, verify_change=True):
    desired_state = copy.deepcopy(desired_state)
    validator.verify(desired_state)
    validator.verify_capabilities(desired_state, netinfo.capabilities())
    validator.verify_dhcp(desired_state)

    _apply_ifaces_state(state.State(desired_state), verify_change)


def _apply_ifaces_state(desired_state, verify_change):
    current_state = state.State({Constants.INTERFACES: netinfo.interfaces()})

    desired_state.sanitize_ethernet(current_state)
    desired_state.sanitize_dynamic_ip()

    metadata.generate_ifaces_metadata(desired_state, current_state)

    with _transaction():
        with _setup_providers():
            _add_interfaces(desired_state.interfaces, current_state.interfaces)
        with _setup_providers():
            current_state = state.State(
                {Constants.INTERFACES: netinfo.interfaces()}
            )
            _edit_interfaces(desired_state.interfaces,
                             current_state.interfaces)
        if verify_change:
            _verify_change(desired_state)


def _verify_change(desired_state):
    desired_state.remove_absent_interfaces()
    desired_state.remove_down_virt_interfaces()

    metadata.remove_ifaces_metadata(desired_state)

    current_state = state.State({Constants.INTERFACES: netinfo.interfaces()})
    assert_ifaces_state(desired_state, current_state)


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


def assert_ifaces_state(desired_state, current_state):
    ifaces_desired_state = desired_state.interfaces
    ifaces_current_state = current_state.interfaces
    if not (set(ifaces_desired_state) <= set(ifaces_current_state)):
        raise NmstateVerificationError(
            format_desired_current_state_diff(ifaces_desired_state,
                                              ifaces_current_state))

    current_state.sanitize_dynamic_ip()
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
    for ifstate in (desired_state, current_state):
        ifstate.get('link-aggregation', {}).get('slaves', []).sort()
    return desired_state, current_state


def _sort_bridge_ports(desired_state, current_state):
    for ifstate in (desired_state, current_state):
        ifstate.get('bridge', {}).get('port', []).sort(key=itemgetter('name'))
    return desired_state, current_state


def _remove_iface_ipv6_link_local_addr(desired_state, current_state):
    for ifstate in (desired_state, current_state):
        ifstate['ipv6']['address'] = list(
            addr for addr in ifstate['ipv6']['address']
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
    for ifstate in (desired_state, current_state):
        for family in ('ipv4', 'ipv6'):
            ifstate.get(family, {}).get('address', []).sort(
                key=itemgetter('ip'))
    return desired_state, current_state
