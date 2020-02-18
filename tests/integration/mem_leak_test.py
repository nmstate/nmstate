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

import libnmstate
import os
import time


def get_current_open_fd():
    return len(os.listdir("/proc/self/fd"))


def test_libnmstate_show_fd_leak():
    original_fd = get_current_open_fd()
    for x in range(0, 100):
        libnmstate.show()
    time.sleep(0.1)  # Wait sysfs/proc been updated.
    assert get_current_open_fd() == original_fd
