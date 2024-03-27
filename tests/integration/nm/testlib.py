# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
