#
# Copyright (c) 2018-2021 Red Hat, Inc.
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
import logging
import time


from libnmstate import validator
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface

from .net_state import NetState
from .nmstate import create_checkpoints
from .nmstate import destroy_checkpoints
from .nmstate import plugin_context
from .nmstate import plugins_capabilities
from .nmstate import remove_metadata_leftover
from .nmstate import rollback_checkpoints
from .nmstate import show_with_plugins
from .state import hide_the_secrets
from .state import remove_the_reserved_secrets
from .version import get_version

VERIFY_RETRY_INTERNAL = 1
VERIFY_RETRY_COUNT = 5
VERIFY_RETRY_COUNT_SRIOV = 60


def apply(
    desired_state,
    *,
    verify_change=True,
    commit=True,
    rollback_timeout=60,
    save_to_disk=True,
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
    logging.debug(f"Nmstate version: {get_version()}")

    desired_state_without_secrets = copy.deepcopy(desired_state)
    hide_the_secrets(desired_state_without_secrets)
    logging.debug(f"Applying desire state: {desired_state_without_secrets}")

    desired_state = copy.deepcopy(desired_state)
    remove_the_reserved_secrets(desired_state)

    with plugin_context() as plugins:
        validator.schema_validate(desired_state)
        current_state = show_with_plugins(
            plugins, include_status_data=True, include_secrets=True
        )
        validator.validate_capabilities(
            copy.deepcopy(desired_state), plugins_capabilities(plugins)
        )
        ignored_ifnames = _get_ignored_interface_names(plugins)
        net_state = NetState(
            desired_state, ignored_ifnames, current_state, save_to_disk
        )
        checkpoints = create_checkpoints(plugins, rollback_timeout)
        # When we have VF count changes and missing eth, it might be user
        # referring future VF in the same desire state, we just apply
        # VF changes state only first.
        if net_state.ifaces.has_vf_count_change_and_missing_eth():
            sriov_ifaces = net_state.ifaces.get_sriov_pf_ifaces()
            if sriov_ifaces:
                pf_net_state = NetState(
                    {Interface.KEY: sriov_ifaces},
                    ignored_ifnames,
                    current_state,
                    save_to_disk,
                )
                _apply_ifaces_state(
                    plugins,
                    pf_net_state,
                    verify_change,
                    save_to_disk,
                    VERIFY_RETRY_COUNT_SRIOV,
                )
                # Refresh the current state
                current_state = show_with_plugins(
                    plugins, include_status_data=True, include_secrets=True
                )
                validator.validate_capabilities(
                    desired_state, plugins_capabilities(plugins)
                )
                ignored_ifnames = _get_ignored_interface_names(plugins)
                net_state = NetState(
                    copy.deepcopy(desired_state),
                    ignored_ifnames,
                    current_state,
                    save_to_disk,
                )
        if net_state.ifaces.has_sriov_iface():
            # If SR-IOV is present, the verification timeout is being increased
            # to avoid timeouts due to slow drivers like i40e.
            verify_retry = VERIFY_RETRY_COUNT_SRIOV
        else:
            verify_retry = VERIFY_RETRY_COUNT
        _apply_ifaces_state(
            plugins, net_state, verify_change, save_to_disk, verify_retry
        )
        if commit:
            destroy_checkpoints(plugins, checkpoints)
        else:
            return checkpoints


def commit(*, checkpoint=None):
    """
    Commit a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to commit. If not specified, a checkpoint
        will be selected and committed.
    :type checkpoint: str
    """
    with plugin_context() as plugins:
        destroy_checkpoints(plugins, checkpoint)


def rollback(*, checkpoint=None):
    """
    Roll back a checkpoint that was received from `apply()`.

    :param checkpoint: Checkpoint to roll back. If not specified, a checkpoint
        will be selected and rolled back.
    :type checkpoint: str
    """
    with plugin_context() as plugins:
        rollback_checkpoints(plugins, checkpoint)


def _apply_ifaces_state(
    plugins, net_state, verify_change, save_to_disk, verify_retry
):
    for plugin in plugins:
        plugin.apply_changes(net_state, save_to_disk)

    verified = False
    if verify_change:
        for _ in range(verify_retry):
            try:
                _verify_change(plugins, net_state)
                verified = True
                break
            except NmstateVerificationError:
                time.sleep(VERIFY_RETRY_INTERNAL)
        if not verified:
            _verify_change(plugins, net_state)


def _verify_change(plugins, net_state):
    current_state = remove_metadata_leftover(
        show_with_plugins(plugins, include_secrets=True)
    )
    net_state.verify(current_state)


def _get_ignored_interface_names(plugins):
    ifaces = set()
    for plugin in plugins:
        for iface_name in plugin.get_ignored_kernel_interface_names():
            ifaces.add(iface_name)

    return ifaces
