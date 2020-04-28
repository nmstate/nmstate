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
import time

from libnmstate import metadata
from libnmstate import nm
from libnmstate import state
from libnmstate import validator
from libnmstate.error import NmstateConflictError
from libnmstate.error import NmstateError
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstatePermissionError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError

from libnmstate.nm import mainloop as nm_mainloop

from .nmstate import plugin_context
from .nmstate import show_with_plugin

MAINLOOP_TIMEOUT = 35
VERIFY_RETRY_INTERNAL = 1
VERIFY_RETRY_TIMEOUT = 5


def apply(
    desired_state, *, verify_change=True, commit=True, rollback_timeout=60
):
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
    with plugin_context() as plugin:
        validator.validate(desired_state)
        validator.validate_capabilities(desired_state, plugin.capabilities)
        validator.validate_unique_interface_name(desired_state)
        validator.validate_dhcp(desired_state)
        validator.validate_dns(desired_state)
        validator.validate_vxlan(desired_state)
        validator.validate_bridge(desired_state)
        checkpoint = _apply_ifaces_state(
            plugin,
            state.State(desired_state),
            verify_change,
            commit,
            rollback_timeout,
        )
        if checkpoint:
            return str(checkpoint.dbuspath)


def commit(*, checkpoint=None):
    """
    Commit a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to commit. If not specified, a checkpoint
        will be selected and committed.
    :type checkpoint: str
    """
    with plugin_context() as plugin:
        nmcheckpoint = _choose_checkpoint(plugin, checkpoint)
        try:
            nmcheckpoint.destroy()
        except nm.checkpoint.NMCheckPointError as e:
            raise NmstateValueError(str(e))


def rollback(*, checkpoint=None):
    """
    Roll back a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to roll back. If not specified, a checkpoint
        will be selected and rolled back.
    :type checkpoint: str
    """
    with plugin_context() as plugin:
        nmcheckpoint = _choose_checkpoint(plugin, checkpoint)
        try:
            nmcheckpoint.rollback()
        except nm.checkpoint.NMCheckPointError as e:
            raise NmstateValueError(str(e))


def _choose_checkpoint(plugin, dbuspath):
    if not dbuspath:
        candidates = nm.checkpoint.get_checkpoints(plugin.client)
        if candidates:
            dbuspath = candidates[0]

    if not dbuspath:
        raise NmstateValueError("No checkpoint specified or found")
    checkpoint = nm.checkpoint.CheckPoint(plugin.context, dbuspath=dbuspath)
    return checkpoint


def _apply_ifaces_state(
    plugin, desired_state, verify_change, commit, rollback_timeout
):
    original_desired_state = copy.deepcopy(desired_state)
    current_state = state.State(show_with_plugin(plugin))

    desired_state.sanitize_ethernet(current_state)
    desired_state.sanitize_dynamic_ip()
    desired_state.merge_routes(current_state)
    desired_state.merge_dns(current_state)
    desired_state.merge_route_rules(current_state)
    desired_state.remove_unknown_interfaces()
    desired_state.complement_master_interfaces_removal(current_state)
    metadata.generate_ifaces_metadata(
        plugin.client, desired_state, current_state
    )

    validator.validate_interfaces_state(original_desired_state, current_state)
    validator.validate_routes(desired_state, current_state)

    try:
        with nm.checkpoint.CheckPoint(
            plugin.context, autodestroy=commit, timeout=rollback_timeout
        ) as checkpoint:
            with _setup_providers():
                state2edit = state.State(desired_state.state)
                state2edit.merge_interfaces(current_state)
                nm.applier.apply_changes(
                    plugin.client,
                    list(state2edit.interfaces.values()),
                    original_desired_state,
                )
            verified = False
            if verify_change:
                for _ in range(VERIFY_RETRY_TIMEOUT):
                    try:
                        _verify_change(plugin, desired_state)
                        verified = True
                        break
                    except NmstateVerificationError:
                        time.sleep(VERIFY_RETRY_INTERNAL)
                if not verified:
                    _verify_change(plugin, desired_state)

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


def _verify_change(plugin, desired_state):
    current_state = state.State(show_with_plugin(plugin))
    verifiable_desired_state = copy.deepcopy(desired_state)
    verifiable_desired_state.verify_interfaces(current_state)
    verifiable_desired_state.verify_routes(current_state)
    verifiable_desired_state.verify_dns(current_state)
    verifiable_desired_state.verify_route_rule(current_state)


@contextmanager
def _setup_providers():
    mainloop = nm_mainloop.mainloop()
    yield
    try:
        mainloop.run(timeout=MAINLOOP_TIMEOUT)
    except NmstateLibnmError:
        nm_mainloop.mainloop(refresh=True)
        raise
