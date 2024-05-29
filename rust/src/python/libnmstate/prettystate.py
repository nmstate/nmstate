# SPDX-License-Identifier: LGPL-2.1-or-later

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
