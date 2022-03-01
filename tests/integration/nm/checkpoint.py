#
# Copyright (c) 2019-2021 Red Hat, Inc.
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

import time

import pytest

from libnmstate.nm.checkpoint import CheckPoint
from libnmstate.nm.checkpoint import get_checkpoints
from libnmstate.error import NmstateConflictError
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstateValueError
from libnmstate.nm.plugin import NetworkManagerPlugin
from libnmstate.nm.context import NmContext


@pytest.fixture(scope="function")
def nm_plugin():
    plugin = NetworkManagerPlugin()
    yield plugin
    if plugin.checkpoint:
        # Ignore failures as the checkpoint might already expired
        try:
            plugin.rollback_checkpoint()
        except Exception:
            pass
    plugin.unload()


@pytest.fixture(scope="function")
def nm_context():
    ctx = NmContext()
    yield ctx
    ctx.clean_up()


def test_creating_one_checkpoint(nm_context):
    """I can create a checkpoint"""
    checkpoint = CheckPoint.create(nm_context)
    assert checkpoint is not None
    checkpoint.destroy()


def test_creating_two_checkpoints(nm_context):
    """I cannot create a checkpoint when a checkpoint already exists."""
    checkpoint = CheckPoint.create(nm_context)
    with pytest.raises(NmstateConflictError):
        CheckPoint.create(nm_context)
    assert checkpoint is not None
    checkpoint.destroy()


def test_checkpoint_timeout(nm_context):
    """I can create a checkpoint that is removed after one second."""
    checkpoint_a = CheckPoint.create(nm_context, timeout=1)
    time.sleep(1)
    checkpoint_b = CheckPoint.create(nm_context)

    assert checkpoint_b is not None
    assert checkpoint_a is not None
    checkpoint_b.destroy()


def test_getting_a_checkpoint(nm_context):
    """I can get a list of all checkpoints."""

    checkpoints = get_checkpoints(nm_context.client)

    assert len(checkpoints) == 0

    checkpoint = CheckPoint.create(nm_context)

    checkpoints = get_checkpoints(nm_context.client)

    assert len(checkpoints) == 1
    assert checkpoints[0] == str(checkpoint)
    checkpoint.destroy()


def test_creating_a_checkpoint_from_dbuspath(nm_context):
    initial_checkpoint = CheckPoint.create(nm_context)
    new_checkpoint = CheckPoint(nm_context, dbuspath=str(initial_checkpoint))
    new_checkpoint.destroy()
    assert not get_checkpoints(nm_context.client)


def test_repeat_create_destroy_checkpoint(nm_context):
    for _ in range(0, 1000):
        checkpoint = CheckPoint.create(nm_context)
        checkpoint.destroy()


def test_plugin_load_specific_checkpoint_not_exist(nm_plugin):
    plugin = nm_plugin
    plugin.create_checkpoint()

    with pytest.raises(NmstateValueError):
        plugin.rollback_checkpoint("checkpoint_not_exist")


def test_plugin_load_default_checkpoint(nm_plugin):
    plugin = nm_plugin
    plugin.create_checkpoint()
    plugin.rollback_checkpoint()

    checkpoints = get_checkpoints(nm_plugin.context.client)

    assert plugin.checkpoint is None
    assert len(checkpoints) == 0


def test_plugin_load_default_checkpoint_when_none_avaiable(nm_plugin):
    plugin = nm_plugin
    with pytest.raises(NmstateValueError):
        plugin.rollback_checkpoint()


def test_plugin_create_and_destroy_checkpoint(nm_plugin):
    plugin = nm_plugin
    plugin.create_checkpoint()
    plugin.destroy_checkpoint()

    checkpoints = get_checkpoints(nm_plugin.context.client)
    assert len(checkpoints) == 0


def test_plugin_create_and_rollback_checkpoint(nm_plugin):
    plugin = nm_plugin
    plugin.create_checkpoint()
    plugin.rollback_checkpoint()

    checkpoints = get_checkpoints(nm_plugin.context.client)
    assert len(checkpoints) == 0


def test_plugin_create_checkpoint_and_timeout(nm_plugin):
    plugin = nm_plugin
    plugin.create_checkpoint(timeout=1)
    time.sleep(2)

    with pytest.raises(NmstateLibnmError):
        plugin.rollback_checkpoint()
