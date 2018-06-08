#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from libnmstate import validator

from network_connections import ArgValidator_ListConnections
from network_connections import Cmd
from network_connections import LogLevel
from network_connections import RunEnvironment


def apply(desired_state):
    validator.verify(desired_state)

    _apply_ifaces_state(desired_state)


def _apply_ifaces_state(state):
    run_env = RunEnvironment()


    def fail_log(connections, idx, severity, msg, **kwargs):
        if severity == LogLevel.ERROR:
            print(connections[idx])
            raise RuntimeError(msg)

    def do_nothing(*args, **kwargs):
        pass

    run_env._check_mode_changed = do_nothing
    run_env.log = fail_log

    connections = []
    for interface in  state['interfaces']:
        if interface["state"] == "down":
            del interface["type"]
        else:
            interface["interface_name"] = interface["name"]
        if "ip" in interface:
            addrs = []
            for a in interface["ip"]["addresses"]:
                addrs.append({"address": a["ip"],
                              "prefix": a["prefix-length"]})
            interface["ip"]["address"] = addrs

            del interface["ip"]["addresses"]
            del interface["ip"]["enabled"]

        connections.append(interface)

    # import json; print(json.dumps(connections, indent=4))
    cmd = Cmd.create('nm', run_env=run_env,
                     connections_unvalidated=connections,
                     connection_validator=ArgValidator_ListConnections())
    cmd.run()


class UnsupportedIfaceStateError(Exception):
    pass
