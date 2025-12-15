# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType

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


@contextmanager
def dummy_interface(ifname):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: ifname,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
            }
        ]
    }
    libnmstate.apply(desired_state)
    try:
        yield desired_state
    finally:
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: ifname,
                        Interface.STATE: InterfaceState.ABSENT,
                    }
                ]
            }
        )
