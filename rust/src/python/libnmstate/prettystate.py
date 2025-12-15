# SPDX-License-Identifier: Apache-2.0

from .clib_wrapper import net_state_serialize


class PrettyState:
    def __init__(self, state):
        self.state = state

    @property
    def yaml(self):
        return net_state_serialize(self.state, use_yaml=True)

    @property
    def json(self):
        return net_state_serialize(self.state, use_yaml=False)
