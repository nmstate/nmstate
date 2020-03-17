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

from contextlib import contextmanager
import time

from . import cmdlib


@contextmanager
def disable_service(service):
    cmdlib.exec_cmd(("systemctl", "stop", service), check=True)
    try:
        yield
    finally:
        cmdlib.exec_cmd(("systemctl", "start", service), check=True)
        ret, _, _ = cmdlib.exec_cmd(("systemctl", "status", service))
        timeout = 5
        while timeout > 0:
            if ret == 0:
                break
            time.sleep(1)
            timeout -= 1
            ret, _, _ = cmdlib.exec_cmd(("systemctl", "status", service))
