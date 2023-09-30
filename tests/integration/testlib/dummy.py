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

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from . import cmdlib


@contextmanager
def nm_unmanaged_dummy(name):
    cmdlib.exec_cmd(f"ip link add name {name} type dummy".split(), check=True)
    cmdlib.exec_cmd(f"ip link set {name} up".split(), check=True)
    cmdlib.exec_cmd(f"nmcli d set {name} managed false".split(), check=True)
    try:
        yield
    finally:
        try:
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: name,
                            Interface.STATE: InterfaceState.ABSENT,
                        }
                    ]
                },
            )
        except Exception:
            # dummy1 might not became managed by NM, hence removal might fail
            cmdlib.exec_cmd(f"ip link del {name}".split())
