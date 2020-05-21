#
# Copyright (c) 2019 Red Hat, Inc.
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
from libnmstate.nm.checkpoint import NMCheckPointCreationError


def test_creating_one_checkpoint(nm_context):
    """ I can create a checkpoint """
    with CheckPoint(nm_context) as checkpoint:
        pass

    assert checkpoint is not None


def test_creating_two_checkpoints(nm_context):
    """ I cannot create a checkpoint when a checkpoint already exists. """
    with CheckPoint(nm_context) as checkpoint:
        with pytest.raises(NMCheckPointCreationError):
            with CheckPoint(nm_context):
                pass

    assert checkpoint is not None


def test_checkpoint_timeout(nm_context):
    """ I can create a checkpoint that is removed after one second. """
    with CheckPoint(nm_context, timeout=1, autodestroy=False) as checkpoint_a:
        time.sleep(1)
        with CheckPoint(nm_context) as checkpoint_b:
            pass

    assert checkpoint_b is not None
    assert checkpoint_a is not None


def test_getting_a_checkpoint(nm_context):
    """ I can get a list of all checkpoints. """

    checkpoints = get_checkpoints(nm_context.client)

    assert len(checkpoints) == 0

    with CheckPoint(nm_context) as checkpoint:
        nm_context.refresh_content()
        checkpoints = get_checkpoints(nm_context.client)

    assert len(checkpoints) == 1
    assert checkpoints[0] == checkpoint.dbuspath


def test_creating_a_checkpoint_from_dbuspath(nm_context):
    with CheckPoint(nm_context, autodestroy=False) as initial_checkpoint:
        pass
    new_checkpoint = CheckPoint(
        nm_context, dbuspath=initial_checkpoint.dbuspath
    )
    new_checkpoint.destroy()
    assert not get_checkpoints(nm_context.client)


def test_repeat_create_destroy_checkpoint(nm_context):
    for _ in range(0, 1000):
        CheckPoint(nm_context)
