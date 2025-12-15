# SPDX-License-Identifier: Apache-2.0

from collections.abc import Mapping


PASSWORD_HID_BY_NMSTATE = "<_password_hid_by_nmstate>"


def hide_the_secrets(state):
    if isinstance(state, Mapping):
        for key, value in state.items():
            if isinstance(value, Mapping) or isinstance(value, list):
                hide_the_secrets(value)
            elif key.endswith("password") and isinstance(value, str):
                state[key] = PASSWORD_HID_BY_NMSTATE
    elif isinstance(state, list):
        for value in state:
            hide_the_secrets(value)
