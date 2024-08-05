# SPDX-License-Identifier: LGPL-2.1-or-later

import copy

import libnmstate

from libnmstate.schema import Description


def apply_with_description(description, desired_state, *args, **kwargs):
    desired_state = copy.deepcopy(desired_state)
    desired_state[Description.KEY] = description
    libnmstate.apply(desired_state, *args, **kwargs)
