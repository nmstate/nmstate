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

from contextlib import contextmanager
import os

import yaml

import libnmstate


PATH_MAX = 4096


@contextmanager
def example_state(initial, cleanup=None):
    """
    Apply the initial state and optionally the cleanup state at the end
    """

    desired_state = load_example(initial)

    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        if cleanup:
            libnmstate.apply(load_example(cleanup))


def load_example(name):
    """
    Load the state from an example yaml file
    """

    examples = find_examples_dir()

    with open(os.path.join(examples, name)) as yamlfile:
        state = yaml.load(yamlfile, Loader=yaml.SafeLoader)

    return state


def find_examples_dir():
    """
    Look recursively for the directory containing the examples
    """

    path = ""
    parent = "../"
    rootdir = "/"
    examples = None
    for _ in range(PATH_MAX // len("x/")):
        maybe_examples = os.path.abspath(os.path.join(path, "examples"))
        if os.path.isdir(maybe_examples):
            examples = maybe_examples
            break

        if os.path.abspath(path) == rootdir:
            break

        path = parent + path

    if examples:
        return examples
    else:
        raise RuntimeError("Cannot find examples directory")
