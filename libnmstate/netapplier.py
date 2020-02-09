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

from contextlib import contextmanager

import copy
import logging
import time

from libnmstate import metadata
from libnmstate import netinfo
from libnmstate import nm
from libnmstate.nm.nmclient import nmclient_context
from libnmstate import schema
from libnmstate import state
from libnmstate import validator
from libnmstate.error import NmstateConflictError
from libnmstate.error import NmstateError
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstatePermissionError
from libnmstate.error import NmstateValueError
from libnmstate.nm import nmclient

MAINLOOP_TIMEOUT = 35


@nmclient_context
def apply(desired_state, verify_change=True, commit=True, rollback_timeout=60):
    """
    Apply the desired state

    :param verify_change: Check if the outcome state matches the desired state
        and rollback if not.
    :param commit: Commit the changes after verification if the state matches.
    :param rollback_timeout: Revert the changes if they are not commited within
        this timeout (specified in seconds).
    :type verify_change: bool
    :type commit: bool
    :type rollback_timeout: int (seconds)
    :returns: Checkpoint identifier
    :rtype: str
    """
    desired_state = copy.deepcopy(desired_state)
    validator.validate(desired_state)
    validator.validate_capabilities(desired_state, netinfo.capabilities())
    validator.validate_unique_interface_name(desired_state)
    validator.validate_dhcp(desired_state)
    validator.validate_dns(desired_state)
    validator.validate_vxlan(desired_state)

    checkpoint = _apply_ifaces_state(
        state.State(desired_state), verify_change, commit, rollback_timeout
    )
    if checkpoint:
        return str(checkpoint.dbuspath)


def commit(checkpoint=None):
    """
    Commit a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to commit. If not specified, a checkpoint
        will be selected and committed.
    :type checkpoint: str
    """

    nmcheckpoint = _choose_checkpoint(checkpoint)
    try:
        nmcheckpoint.destroy()
    except nm.checkpoint.NMCheckPointError as e:
        raise NmstateValueError(str(e))


def rollback(checkpoint=None):
    """
    Roll back a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to roll back. If not specified, a checkpoint
        will be selected and rolled back.
    :type checkpoint: str
    """

    nmcheckpoint = _choose_checkpoint(checkpoint)
    try:
        nmcheckpoint.rollback()
    except nm.checkpoint.NMCheckPointError as e:
        raise NmstateValueError(str(e))


def _choose_checkpoint(dbuspath):
    if not dbuspath:
        candidates = nm.checkpoint.get_checkpoints()
        if candidates:
            dbuspath = candidates[0]

    if not dbuspath:
        raise NmstateValueError("No checkpoint specified or found")
    checkpoint = nm.checkpoint.CheckPoint(dbuspath=dbuspath)
    return checkpoint


def _apply_ifaces_state(
    desired_state, verify_change, commit, rollback_timeout
):
    current_state = state.State(netinfo.show())

    desired_state.sanitize_ethernet(current_state)
    desired_state.sanitize_dynamic_ip()
    desired_state.merge_routes(current_state)
    desired_state.merge_dns(current_state)
    desired_state.merge_route_rules(current_state)
    desired_state.remove_unknown_interfaces()
    metadata.generate_ifaces_metadata(desired_state, current_state)

    validator.validate_interfaces_state(desired_state, current_state)
    validator.validate_routes(desired_state, current_state)

    new_interfaces = _list_new_interfaces(desired_state, current_state)

    try:
        with nm.checkpoint.CheckPoint(
            autodestroy=commit, timeout=rollback_timeout
        ) as checkpoint:
            with _setup_providers():
                ifaces2add, ifaces_add_configs = _add_interfaces(
                    new_interfaces, desired_state
                )
                state2edit = _create_editable_desired_state(
                    desired_state, current_state, new_interfaces
                )
                ifaces2edit, ifaces_edit_configs = _edit_interfaces(state2edit)
                nm.applier.set_ifaces_admin_state(
                    ifaces2add + ifaces2edit,
                    con_profiles=ifaces_add_configs + ifaces_edit_configs,
                )
            if verify_change:
                _verify_change(desired_state)
        if not commit:
            return checkpoint
    except nm.checkpoint.NMCheckPointPermissionError:
        raise NmstatePermissionError("Error creating a check point")
    except nm.checkpoint.NMCheckPointCreationError:
        raise NmstateConflictError("Error creating a check point")
    except NmstateError:
        # Assume rollback occurred.
        # Checkpoint rollback is async, there is a need to wait for it to
        # finish before proceeding with other actions.
        time.sleep(5)
        raise


def _create_editable_desired_state(
    desired_state, current_state, new_intefaces
):
    """
    Create a new state object that includes only existing interfaces which need
    to be edited/changed.
    """
    state2edit = state.create_state(
        desired_state.state,
        interfaces_to_filter=(
            set(current_state.interfaces) - set(new_intefaces)
        ),
    )
    state2edit.merge_interfaces(current_state)
    return state2edit


def _list_new_interfaces(desired_state, current_state):
    return [
        name
        for name in desired_state.interfaces.keys()
        - current_state.interfaces.keys()
        if desired_state.interfaces[name].get(schema.Interface.STATE)
        not in (schema.InterfaceState.ABSENT, schema.InterfaceState.DOWN)
    ]


def _verify_change(desired_state):
    current_state = state.State(netinfo.show())
    desired_state.verify_interfaces(current_state)
    desired_state.verify_routes(current_state)
    desired_state.verify_dns(current_state)
    desired_state.verify_route_rule(current_state)


@contextmanager
def _setup_providers():
    mainloop = nmclient.mainloop()
    yield
    try:
        mainloop.run(timeout=MAINLOOP_TIMEOUT)
    except NmstateLibnmError:
        nmclient.mainloop(refresh=True)
        raise


def _add_interfaces(new_interfaces, desired_state):
    logging.debug("Adding new interfaces: %s", new_interfaces)

    ifaces2add = [desired_state.interfaces[name] for name in new_interfaces]

    ifaces2add += nm.applier.prepare_proxy_ifaces_desired_state(ifaces2add)
    ifaces_configs = nm.applier.prepare_new_ifaces_configuration(ifaces2add)
    nm.applier.create_new_ifaces(ifaces_configs)

    return (ifaces2add, ifaces_configs)


def _edit_interfaces(state2edit):
    logging.debug("Editing interfaces: %s", list(state2edit.interfaces))

    ifaces2edit = list(state2edit.interfaces.values())

    iface2prepare = list(
        filter(
            lambda state: state.get("state") not in ("absent", "down"),
            ifaces2edit,
        )
    )
    proxy_ifaces = nm.applier.prepare_proxy_ifaces_desired_state(iface2prepare)
    ifaces_configs = nm.applier.prepare_edited_ifaces_configuration(
        iface2prepare + proxy_ifaces
    )
    nm.applier.edit_existing_ifaces(ifaces_configs)

    return (ifaces2edit + proxy_ifaces, ifaces_configs)


def _index_by_name(ifaces_state):
    return {iface["name"]: iface for iface in ifaces_state}
