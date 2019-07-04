#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

# Naming Schema:
#   * iface_state: The IfaceState containing all the interfaces objects
#   * iface_obj: The BaseInterface object or its inheritance objects
#   * iface_name: String of interface name
#   * conn_setting: The object of nm_connection.ConnectionSetting
#   * profile: The NM.RemoteConnection for NM connection profile(like nmcli c)

from contextlib import contextmanager

from libnmstate.dns import DnsState
from libnmstate.error import NmstateLibnmError
from libnmstate.error import NmstatePermissionError
from libnmstate.iface_state import IfaceState
import libnmstate.nm.checkpoint as nm_checkpoint
import libnmstate.nm.nmclient as nmclient
from libnmstate.route import RouteState
from libnmstate.schema import Interface
from libnmstate.schema import Route
from libnmstate.schema import DNS
from libnmstate.validator import validate as schema_validate


class NmState(object):
    def __init__(self, state_dict=None):
        if state_dict is None:
            self._iface_state = IfaceState()
            self._route_state = RouteState()
            self._dns_state = DnsState()
        else:
            schema_validate(state_dict)
            self._iface_state = IfaceState(
                state_dict.get(Interface.KEY, [])
            )
            self._route_state = RouteState(state_dict.get(Route.KEY, {}))
            self._dns_state = DnsState(state_dict.get(DNS.KEY, {}))

    def apply(self, verify_change=True, commit=True, rollback_timeout=60):
        current_state = NmState()

        # Check whether desire state contain illegal value
        self._iface_state.pre_merge_validate()
        self._dns_state.pre_merge_validate()
        self._route_state.pre_merge_validate()

        self._iface_state.merge_config(current_state)
        self._route_state.merge_config(current_state)
        self._dns_state.merge_config(current_state)

        self._iface_state.sanitize()

        self._iface_state.update_slave_ifaces()
        current_state._iface_state.update_slave_ifaces()

        # Check whether desire state contain missing/invalid slaves and etc
        self._iface_state.post_merge_validate()
        self._dns_state.post_merge_validate()
        self._route_state.post_merge_validate()

        self._iface_state.generate_metadata()
        self._route_state.generate_metadata(self._iface_state)
        self._dns_state.generate_metadata(self._iface_state)

        self._iface_state.remove_unchanged_iface(current_state)

        if not self._iface_state.keys():
            print("nothing changed")
            return

        try:
            with nm_checkpoint.CheckPoint(
                autodestroy=commit, timeout=rollback_timeout
            ) as checkpoint:
                with _setup_providers():
                    self._iface_state.apply()
                if verify_change:
                    current_state = NmState()
                    self._iface_state.verify(current_state)
                    self._route_state.verify(current_state)
                    self._dns_state.verify(current_state)
            if not commit:
                return checkpoint
        except nm_checkpoint.NMCheckPointPermissionError:
            raise NmstatePermissionError('Error creating a check point')
        except nm_checkpoint.NMCheckPointCreationError:
            raise NmstateConflictError('Error creating a check point')

    def to_dict(self):
        return {
            DNS.KEY: self._dns_state.dump(),
            Route.KEY: self._route_state.dump(),
            Interface.KEY: self._iface_state.dump(),
        }

    @property
    def iface_state(self):
        return self._iface_state


@contextmanager
def _setup_providers():
    mainloop = nmclient.mainloop()
    yield
    success = mainloop.run(timeout=20)
    if not success:
        raise NmstateLibnmError(
            'Unexpected failure of libnm when running the mainloop: {}'.format(
                mainloop.error
            )
        )
