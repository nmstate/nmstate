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


def test_creating_one_checkpoint():
    """ I can create a checkpoint """
    with CheckPoint() as checkpoint:
        pass

    assert checkpoint is not None


def test_creating_two_checkpoints():
    """ I cannot create a checkpoint when a checkpoint already exists. """
    with CheckPoint() as checkpoint:
        with pytest.raises(NMCheckPointCreationError):
            with CheckPoint():
                pass

    assert checkpoint is not None


def test_checkpoint_timeout():
    """ I can create a checkpoint that is removed after one second. """

    with pytest.raises(Exception):
        with CheckPoint(timeout=1) as checkpoint_a:
            time.sleep(1)
            with CheckPoint() as checkpoint_b:
                pass

    assert checkpoint_b is not None
    assert checkpoint_a is not None


def test_getting_a_checkpoint():
    """ I can get a list of all checkpoints. """

    checkpoints = get_checkpoints()

    assert len(checkpoints) == 0

    with CheckPoint() as checkpoint:
        checkpoints = get_checkpoints()

    assert len(checkpoints) == 1
    assert checkpoints[0] == checkpoint.dbuspath


def test_non_auto_destroying_checkpoint():
    """ I can create a checkpoint that needs to be confirmed manually. """

    with CheckPoint(autodestroy=False) as checkpoint:
        pass

    checkpoints = get_checkpoints()

    assert checkpoints[0] == checkpoint.dbuspath
    checkpoint.destroy()
    assert not get_checkpoints()


def test_creating_a_checkpoint_from_dbuspath():
    with CheckPoint(autodestroy=False) as initial_checkpoint:
        pass

    new_checkpoint = CheckPoint(dbuspath=initial_checkpoint.dbuspath)
    new_checkpoint.destroy()
    assert not get_checkpoints()
