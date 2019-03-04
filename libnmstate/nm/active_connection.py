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

import logging

from . import nmclient


class AlternativeACState(object):
    UNKNOWN = 0
    ACTIVE = 1
    ACTIVATING = 2
    FAIL = 3


class ActivationError(Exception):
    pass


class ActiveConnection(object):

    def __init__(self, active_connection=None):
        self.handlers = set()
        self._act_con = active_connection
        self._mainloop = nmclient.mainloop()
        self._state = None

        nmdevs = None
        if active_connection:
            nmdevs = active_connection.get_devices()
        self._nmdev = nmdevs[0] if nmdevs else None

        if self._act_con:
            self.refresh_state()

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
                nmclient.NM.ActiveConnectionState.DEACTIVATED):
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
                    'Connection deactivation aborted on %s: error=%s',
                    self._nmdev.get_iface(), e)
            else:
                self._mainloop.quit(
                    'Connection deactivation failed on {}: error={}'.format(
                        self._nmdev.get_iface(), e))
            return

        if success:
            logging.debug(
                'Connection deactivation succeeded on %s',
                self._nmdev.get_iface())
            self._mainloop.execute_next_action()
        else:
            self._mainloop.quit(
                'Connection deactivation failed on %s: error=unknown' %
                self._nmdev.get_iface())

    def refresh_state(self):
        self._state = self._act_con.get_state()
        self._state_reason = self._act_con.get_state_reason()
        self._alternative_state = AlternativeACState.UNKNOWN

        nm_acs = nmclient.NM.ActiveConnectionState
        nm_acsreason = nmclient.NM.ActiveConnectionStateReason
        if self._state == nm_acs.DEACTIVATED:
            unable_to_activate = (
                    not self._nmdev or
                    (
                        self._state_reason is not None and
                        self._state_reason != nm_acsreason.DEVICE_DISCONNECTED
                    ) or
                    self._nmdev.get_active_connection() is not self._act_con
            )
            if unable_to_activate:
                self._alternative_state = AlternativeACState.FAIL
            # Use the device-state as an alternative to determine if active.
            elif (self.nmdev_state <= nmclient.NM.DeviceState.DISCONNECTED or
                    self.nmdev_state > nmclient.NM.DeviceState.DEACTIVATING):
                self._alternative_state = AlternativeACState.FAIL

    @property
    def is_active(self):
        nm_acs = nmclient.NM.ActiveConnectionState
        if self._state == nm_acs.ACTIVATED:
            return True
        elif self._state == nm_acs.ACTIVATING:
                # master connections qualify as activated once they
                # reach IP-Config state. That is because they may
                # wait for slave devices to attach
                return (
                    _is_device_master_type(self._nmdev) and
                    nmclient.NM.DeviceState.IP_CONFIG <= self.nmdev_state <=
                    nmclient.NM.DeviceState.ACTIVATED
                )

        return False

    @property
    def is_activating(self):
        activation_failed = self._alternative_state == AlternativeACState.FAIL
        return not self.is_active and not activation_failed

    @property
    def reason(self):
        return self._state_reason

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
        return self._state

    @property
    def nmdev_state(self):
        return (self._nmdev.get_state() if self._nmdev
                else nmclient.NM.DeviceState.UNKNOWN)


def _is_device_master_type(nmdev):
    if nmdev:
        gobject = nmclient.GObject
        is_master_type = (
            gobject.type_is_a(nmdev, nmclient.NM.DeviceBond) or
            gobject.type_is_a(nmdev, nmclient.NM.DeviceBridge) or
            gobject.type_is_a(nmdev, nmclient.NM.DeviceTeam) or
            gobject.type_is_a(nmdev, nmclient.NM.DeviceOvsBridge)
        )
        return is_master_type
    return False
