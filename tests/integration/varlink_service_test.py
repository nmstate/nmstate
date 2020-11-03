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
import pytest
import varlink
import threading
import subprocess
import sys
import json
import libnmstate
import os
import time

from nmstatectl.nmstate_varlink import gen_varlink_server
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6


VARLINK_INTERFACE = "io.nmstate"

APPLY_STATE = {
    Interface.KEY: [
        {
            Interface.NAME: "varlink_test",
            Interface.TYPE: InterfaceType.DUMMY,
            Interface.STATE: InterfaceState.UP,
            Interface.IPV4: {InterfaceIPv4.ENABLED: False},
            Interface.IPV6: {InterfaceIPv6.ENABLED: False},
        }
    ]
}


@pytest.fixture(
    params=["/run/nmstate"],
    ids=["unix_socket_connection"],
)
def server(request):
    server = gen_varlink_server(request.param)
    thread_server = threading.Thread(target=server.serve_forever, daemon=True)
    thread_server.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture(
    params=["unix:/run/nmstate/nmstate.so"],
    ids=["systemd_unix_connection"],
)
def systemd_service(request):
    if os.system("systemctl is-active nmstate-varlink.service") != 0:
        os.system("systemctl start nmstate-varlink.service")
        time.sleep(1)
    yield request.param
    os.system("systemctl stop nmstate-varlink.service")


def _format_address(server_address):
    return f"unix:{server_address}"


def test_varlink_show(server):
    lib_state = libnmstate.show()
    with varlink.Client(_format_address(server.server_address)).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        varlink_state = con._call("Show")
        assert varlink_state["state"] == lib_state


def test_varlink_apply_state(server):
    with varlink.Client(_format_address(server.server_address)).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        con._call("Apply", {"desired_state": APPLY_STATE})
        lib_state = libnmstate.show()
        assert any(
            interface
            for interface in lib_state[Interface.KEY]
            if interface[Interface.NAME]
            == APPLY_STATE[Interface.KEY][0][Interface.NAME]
        )
        APPLY_STATE[Interface.KEY][0][Interface.STATE] = InterfaceState.DOWN
        libnmstate.apply(APPLY_STATE)


def test_varlink_apply_with_none_state(server):
    apply_state = {"desired_state": {}}
    with varlink.Client(_format_address(server.server_address)).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        with pytest.raises(varlink.InvalidParameter):
            con._call("Apply", apply_state)


def test_varlink_commit_error(server):
    with varlink.Client(_format_address(server.server_address)).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        with pytest.raises(varlink.VarlinkError):
            con._call("Commit", None)


def test_varlink_rollback_error(server):
    with varlink.Client(_format_address(server.server_address)).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        with pytest.raises(varlink.VarlinkError):
            con._call("Rollback", None)


def test_varlink_activation_mode():
    lib_state = libnmstate.show()
    command = (
        "varlink --activate='nmstatectl varlink /run/nmstate' "
        + "call io.nmstate.Show"
    )
    output = subprocess.check_output(command, shell=True).decode(
        sys.stdout.encoding
    )
    parsed_out = json.loads(output)
    assert parsed_out["state"] == lib_state


def test_systemd_varlink_show(systemd_service):
    lib_state = libnmstate.show()
    with varlink.Client(systemd_service).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        varlink_state = con._call("Show")
        assert varlink_state["state"] == lib_state


def test_systemd_varlink_apply_state(systemd_service):
    APPLY_STATE[Interface.KEY][0][Interface.STATE] = InterfaceState.UP
    with varlink.Client(systemd_service).open(
        VARLINK_INTERFACE, namespaced=False
    ) as con:
        con._call("Apply", {"desired_state": APPLY_STATE})
        lib_state = libnmstate.show()
        assert any(
            interface
            for interface in lib_state[Interface.KEY]
            if interface[Interface.NAME]
            == APPLY_STATE[Interface.KEY][0][Interface.NAME]
        )
        APPLY_STATE[Interface.KEY][0][Interface.STATE] = InterfaceState.DOWN
        libnmstate.apply(APPLY_STATE)
