# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager

from libnmstate import error

from ..testlib import cmdlib


class MainloopTestError(Exception):
    pass


@contextmanager
def main_context(ctx):
    yield
    try:
        ctx.wait_all_finish()
    except error.NmstateLibnmError as ex:
        raise MainloopTestError(str(ex.args))


def get_nm_active_profiles():
    all_profile_names_output = cmdlib.exec_cmd(
        "nmcli -g NAME connection show --active".split(" "), check=True
    )[1]
    all_profile_uuids_output = cmdlib.exec_cmd(
        "nmcli -g UUID connection show --active".split(" "), check=True
    )[1]
    return (
        all_profile_names_output.split("\n"),
        all_profile_uuids_output.split("\n"),
    )


def get_proxy_port_profile_uuid_of_ovs_interface(iface_name):
    proxy_port_uuid = cmdlib.exec_cmd(
        f"nmcli -g connection.master connection show {iface_name}".split(" "),
        check=True,
    )[1].strip()
    cmdlib.exec_cmd(
        f"nmcli -g connection.id connection show {proxy_port_uuid}".split(" "),
        check=True,
    )
    return proxy_port_uuid


def iface_hold_in_memory_connection(iface_name):
    output = cmdlib.exec_cmd(
        f"nmcli -g FILENAME,DEVICE c show  --active".split(),
        check=True,
    )[1].strip()
    for line in output.split("\n"):
        if line.endswith(f":{iface_name}"):
            return line.startswith("/run/")
    return False
