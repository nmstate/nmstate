# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from . import cmdlib


@contextmanager
def nm_unmanaged_dummy(name):
    cmdlib.exec_cmd(f"ip link del {name}".split(), check=False)
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
