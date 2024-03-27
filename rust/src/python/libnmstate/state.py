# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2020 Red Hat, Inc.
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
