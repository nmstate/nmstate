# SPDX-License-Identifier: Apache-2.0

import copy

import libnmstate

from libnmstate.schema import Description


def apply_with_description(description, desired_state, *args, **kwargs):
    desired_state = copy.deepcopy(desired_state)
    desired_state[Description.KEY] = description
    libnmstate.apply(desired_state, *args, **kwargs)
