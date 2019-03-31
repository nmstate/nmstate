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

import copy
import six

from libnmstate import metadata
from libnmstate import netinfo
from libnmstate import nm
from libnmstate import state
from libnmstate import validator
from libnmstate.error import NmstateLibnmError
from libnmstate.nm import nmclient
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
            _edit_interfaces(desired_state, current_state)
        if verify_change:
            _verify_change(desired_state)


def _verify_change(desired_state):
    current_state = state.State({Constants.INTERFACES: netinfo.interfaces()})
    desired_state.verify_interfaces(current_state)


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


def _edit_interfaces(desired_state, current_state):
    state2edit = state.create_state(
        desired_state.state,
        interfaces_to_filter=set(current_state.interfaces)
    )
    state2edit.merge_interfaces(current_state)
    ifaces2edit = list(six.viewvalues(state2edit.interfaces))

    validator.verify_interfaces_state(ifaces2edit, desired_state.interfaces)

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


def _index_by_name(ifaces_state):
    return {iface['name']: iface for iface in ifaces_state}
