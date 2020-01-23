#
# Copyright (c) 2019 Red Hat, Inc.
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

import logging

from . import nmclient
from . import ipv4
from . import ipv6
from .nmclient import GLib
from .nmclient import NM


class ActivationError(Exception):
    pass


class ActiveConnection:
    def __init__(self, active_connection=None):
        self.handlers = set()
        self.device_handlers = set()
        self._act_con = active_connection
        self._mainloop = nmclient.mainloop()

        nmdevs = None
        if active_connection:
            nmdevs = active_connection.get_devices()
        self._nmdev = nmdevs[0] if nmdevs else None

    def import_by_device(self, nmdev=None):
        assert self._act_con is None

        if nmdev:
            self._nmdev = nmdev
        if self._nmdev:
            self._act_con = self._nmdev.get_active_connection()

    def deactivate(self):
        """
        Deactivating the current active connection,
        The profile itself is not removed.

        For software devices, deactivation removes the devices from the kernel.
        """
        self._mainloop.push_action(self._safe_deactivate_async)

    def _safe_deactivate_async(self):
        act_connection = self._nmdev.get_active_connection()
        mainloop = nmclient.mainloop()
        if not act_connection or act_connection.props.state in (
            nmclient.NM.ActiveConnectionState.DEACTIVATING,
            nmclient.NM.ActiveConnectionState.DEACTIVATED,
        ):
            # Nothing left to do here, call the next action.
            mainloop.execute_next_action()
            return

        user_data = None
        client = nmclient.client()
        client.deactivate_connection_async(
            act_connection,
            mainloop.cancellable,
            self._deactivate_connection_callback,
            user_data,
        )

    def _deactivate_connection_callback(self, src_object, result, user_data):
        try:
            success = src_object.deactivate_connection_finish(result)
        except Exception as e:
            if self._mainloop.is_action_canceled(e):
                logging.debug(
                    "Connection deactivation aborted on %s: error=%s",
                    self._nmdev.get_iface(),
                    e,
                )
            else:
                if (
                    isinstance(e, GLib.GError)
                    # pylint: disable=no-member
                    and e.domain == nmclient.NM_MANAGER_ERROR_DOMAIN
                    and e.code == NM.ManagerError.CONNECTIONNOTACTIVE
                    # pylint: enable=no-member
                ):
                    success = True
                    logging.debug(
                        "Connection is not active on {}, no need to "
                        "deactivate".format(self.devname)
                    )
                else:
                    self._mainloop.quit(
                        "Connection deactivation failed on {}: "
                        "error={}".format(self._nmdev.get_iface(), e)
                    )
                    return

        if success:
            logging.debug(
                "Connection deactivation succeeded on %s",
                self._nmdev.get_iface(),
            )
            self._mainloop.execute_next_action()
        else:
            self._mainloop.quit(
                "Connection deactivation failed on %s: error=unknown"
                % self._nmdev.get_iface()
            )

    @property
    def is_active(self):
        nm_acs = nmclient.NM.ActiveConnectionState
        if self.state == nm_acs.ACTIVATED:
            return True
        elif self.state == nm_acs.ACTIVATING:
            ac_state_flags = self.nm_active_connection.get_state_flags()
            nm_flags = NM.ActivationStateFlags
            ip4_is_dynamic = ipv4.is_dynamic(self.nm_active_connection)
            ip6_is_dynamic = ipv6.is_dynamic(self.nm_active_connection)
            if (
                _is_device_master_type(self._nmdev)
                or (ip4_is_dynamic and ac_state_flags & nm_flags.IP6_READY)
                or (ip6_is_dynamic and ac_state_flags & nm_flags.IP4_READY)
                or (ip4_is_dynamic and ip6_is_dynamic)
            ):
                # For interface meet any condition below will be
                # treated as activated when reach IP_CONFIG state:
                #   * Is master device.
                #   * DHCPv4 enabled with IP6_READY flag.
                #   * DHCPv6/Autoconf with IP4_READY flag.
                #   * DHCPv4 enabled with DHCPv6/Autoconf enabled.
                return (
                    nmclient.NM.DeviceState.IP_CONFIG
                    <= self.nmdev_state
                    <= nmclient.NM.DeviceState.ACTIVATED
                )

        return False

    @property
    def is_activating(self):
        return (
            self.state == nmclient.NM.ActiveConnectionState.ACTIVATING
            and not self.is_active
        )

    @property
    def reason(self):
        return self._act_con.get_state_reason()

    @property
    def nm_active_connection(self):
        return self._act_con

    @property
    def devname(self):
        return self._nmdev.get_iface()

    @property
    def nmdevice(self):
        return self._nmdev

    @nmdevice.setter
    def nmdevice(self, nmdev):
        assert self._nmdev is None
        self._nmdev = nmdev

    @property
    def state(self):
        return self._act_con.get_state()

    @property
    def nmdev_state(self):
        return (
            self._nmdev.get_state()
            if self._nmdev
            else nmclient.NM.DeviceState.UNKNOWN
        )

    def remove_handlers(self):
        for handler_id in self.handlers:
            self.nm_active_connection.handler_disconnect(handler_id)
        self.handlers = set()
        for handler_id in self.device_handlers:
            self.nmdevice.handler_disconnect(handler_id)
        self.device_handlers = set()


def _is_device_master_type(nmdev):
    if nmdev:
        gobject = nmclient.GObject
        is_master_type = (
            gobject.type_is_a(nmdev, nmclient.NM.DeviceBond)
            or gobject.type_is_a(nmdev, nmclient.NM.DeviceBridge)
            or gobject.type_is_a(nmdev, nmclient.NM.DeviceTeam)
            or gobject.type_is_a(nmdev, nmclient.NM.DeviceOvsBridge)
        )
        return is_master_type
    return False
