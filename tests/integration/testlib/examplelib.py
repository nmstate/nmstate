# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import os

import yaml

import libnmstate

PATH_MAX = 4096


@contextmanager
def example_state(initial, cleanup=None, substitute=None):
    """
    Apply the initial state and optionally the cleanup state at the end
    """

    desired_state = load_example(initial, substitute)

    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        if cleanup:
            try:
                libnmstate.apply(
                    load_example(cleanup, substitute), verify_change=True
                )
            except libnmstate.error.NmstateVerificationError:
                libnmstate.apply(
                    load_example(cleanup, substitute), verify_change=False
                )
                raise


def load_example(name, substitute=None):
    """
    Load the state from an example yaml file
    """

    examples = find_examples_dir()

    with open(os.path.join(examples, name)) as yamlfile:
        yaml_str = yamlfile.read()
        if substitute:
            yaml_str = yaml_str.replace(substitute[0], substitute[1])
        state = yaml.load(yaml_str, Loader=yaml.SafeLoader)

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
