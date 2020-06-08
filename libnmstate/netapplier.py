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

import copy
import time

from libnmstate import validator
from libnmstate.error import NmstateVerificationError

from .nmstate import plugin_context
from .nmstate import show_with_plugin
from .net_state import NetState

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
        validator.schema_validate(desired_state)
        validator.validate_capabilities(desired_state, plugin.capabilities)
        current_state = show_with_plugin(plugin)
        net_state = NetState(desired_state, current_state)
        checkpoint = plugin.create_checkpoint(rollback_timeout)
        _apply_ifaces_state(plugin, net_state, verify_change)
        if commit:
            plugin.destroy_checkpoint(checkpoint)
        else:
            return checkpoint


def commit(*, checkpoint=None):
    """
    Commit a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to commit. If not specified, a checkpoint
        will be selected and committed.
    :type checkpoint: str
    """
    with plugin_context() as plugin:
        plugin.destroy_checkpoint(checkpoint)


def rollback(*, checkpoint=None):
    """
    Roll back a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to roll back. If not specified, a checkpoint
        will be selected and rolled back.
    :type checkpoint: str
    """
    with plugin_context() as plugin:
        plugin.rollback_checkpoint(checkpoint)


def _apply_ifaces_state(plugin, net_state, verify_change):
    plugin.apply_changes(net_state)
    verified = False
    if verify_change:
        for _ in range(VERIFY_RETRY_TIMEOUT):
            try:
                _verify_change(plugin, net_state)
                verified = True
                break
            except NmstateVerificationError:
                time.sleep(VERIFY_RETRY_INTERNAL)
        if not verified:
            _verify_change(plugin, net_state)


def _verify_change(plugin, net_state):
    current_state = show_with_plugin(plugin)
    net_state.verify(current_state)
