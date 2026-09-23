# SPDX-License-Identifier: Apache-2.0

import os
from contextlib import contextmanager

import libnmstate
from libnmstate.schema import DNS
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import OVSBridge
from libnmstate.schema import Route
from libnmstate.schema import RouteRule

from .cmdlib import exec_cmd

NM_CONN_FOLDER = "/etc/NetworkManager/system-connections"

_OVS_IFACE_TYPES = (
    InterfaceType.OVS_BRIDGE,
    InterfaceType.OVS_INTERFACE,
)


def _cleanup_iface(iface, state):
    cleanup_iface = {
        Interface.NAME: iface[Interface.NAME],
        Interface.STATE: state,
    }
    if Interface.TYPE in iface:
        cleanup_iface[Interface.TYPE] = iface[Interface.TYPE]
    return cleanup_iface


def _cleanup_ifaces(desire_state, state):
    return [
        _cleanup_iface(iface, state)
        for iface in desire_state.get(Interface.KEY, [])
    ]


def _ovs_bridge_port_names(desire_state):
    port_names = set()
    for iface in desire_state.get(Interface.KEY, []):
        if iface.get(Interface.TYPE) != InterfaceType.OVS_BRIDGE:
            continue
        ports = (
            iface.get(OVSBridge.CONFIG_SUBTREE, {}).get(OVSBridge.PORT_SUBTREE)
            or []
        )
        for port in ports:
            name = port.get(OVSBridge.Port.NAME)
            if name:
                port_names.add(name)
    return port_names


def _ovs_down_ifaces(desire_state):
    """OVS bridge/interfaces and their system ports need DOWN before ABSENT."""
    port_names = _ovs_bridge_port_names(desire_state)
    down_ifaces = []
    for iface in desire_state.get(Interface.KEY, []):
        if (
            iface.get(Interface.TYPE) in _OVS_IFACE_TYPES
            or iface[Interface.NAME] in port_names
        ):
            down_ifaces.append(_cleanup_iface(iface, InterfaceState.DOWN))
    return down_ifaces


@contextmanager
def gen_conf_apply(desire_state):
    file_paths = []
    try:
        conns = libnmstate.generate_configurations(desire_state).get(
            "NetworkManager", []
        )
        for conn in conns:
            file_paths.append(save_nmconnection(conn[0], conn[1]))
        for file_path in file_paths:
            load_nm_connection(file_path)
        activate_all_nm_connections()
        yield
    finally:
        # OVS needs selected interfaces brought down before absent so ports
        # detach from the bridge cleanly. Keep ABSENT/file cleanup in a
        # nested finally so a DOWN failure cannot skip them.
        try:
            down_ifaces = _ovs_down_ifaces(desire_state)
            if down_ifaces:
                libnmstate.apply({Interface.KEY: down_ifaces})
        finally:
            try:
                cleanup_absent = {
                    DNS.KEY: {DNS.CONFIG: {}},
                    Interface.KEY: _cleanup_ifaces(
                        desire_state, InterfaceState.ABSENT
                    ),
                    Route.KEY: {
                        Route.CONFIG: [{Route.STATE: Route.STATE_ABSENT}]
                    },
                    RouteRule.KEY: {
                        RouteRule.CONFIG: [
                            {RouteRule.STATE: RouteRule.STATE_ABSENT}
                        ]
                    },
                }
                libnmstate.apply(cleanup_absent)
            finally:
                for file_path in file_paths:
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass


def save_nmconnection(file_name, content):
    file_path = f"{NM_CONN_FOLDER}/{file_name}"
    with open(file_path, "w") as fd:
        fd.write(content)
    os.chmod(file_path, 0o600)
    os.chown(file_path, 0, 0)
    return file_path


def load_nm_connection(file_path):
    exec_cmd(f"nmcli c load {file_path}".split(), check=True)


def activate_all_nm_connections():
    con_ids = exec_cmd("nmcli -g UUID c".split(), check=True)[1].split("\n")
    for con_id in con_ids:
        exec_cmd(f"nmcli c up {con_id}".split(), check=False)
