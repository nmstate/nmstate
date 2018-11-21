#
# Copyright 2018 Red Hat, Inc.
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


class ActivationError(Exception):
    pass


class AlternativeACState(object):
    UNKNOWN = 0
    ACTIVE = 1
    ACTIVATING = 2
    FAIL = 3


class ActiveConnection(object):

    def __init__(self, active_connection):
        self._act_con = active_connection
        nmdevs = active_connection.get_devices()
        self._nmdev = nmdevs[0] if nmdevs else None

        self.handlers = set()

        self.refresh_state()

    def refresh_state(self):
        self._state = self._act_con.get_state()
        self._state_reason = self._act_con.get_state_reason()
        self._alternative_state = AlternativeACState.UNKNOWN

        nm_acs = nmclient.NM.ActiveConnectionState
        if self._state == nm_acs.DEACTIVATED:
            unable_to_activate = (
                    not self._nmdev or
                    (
                            self._state_reason is not None and
                            self._state_reason != nm_acs.DEVICE_DISCONNECTED
                    ) or
                    self._nmdev.get_active_connection() is not self._act_con
            )
            if unable_to_activate:
                self._alternative_state = AlternativeACState.FAIL
            # Use the device-state as an alternative to determine if active.
            elif (self._nmdev <= nmclient.NM.DeviceState.DISCONNECTED or
                    self._nmdev > nmclient.NM.DeviceState.DEACTIVATING):
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
                nmdev_state = (self._nmdev.get_state() if self._nmdev
                               else nmclient.NM.DeviceState.UNKNOWN)
                return (
                    _is_device_master_type(self._nmdev) and
                    nmclient.NM.DeviceState.IP_CONFIG <= nmdev_state <=
                    nmclient.NM.DeviceState.ACTIVATED
                )

        return False

    @property
    def is_activating(self):
        activation_failed = (
            not self.is_active and
            self._alternative_state == AlternativeACState.FAIL
        )
        return not activation_failed

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
    def state(self):
        return self._state


def activate(dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    mainloop = nmclient.mainloop()
    mainloop.push_action(
        _safe_activate_async, dev, connection_id)


def _safe_activate_async(dev, connection_id):
    client = nmclient.client()
    mainloop = nmclient.mainloop()
    connection = None
    if connection_id:
        connection = client.get_connection_by_id(connection_id)
    specific_object = None
    user_data = mainloop, dev
    client.activate_connection_async(
        connection,
        dev,
        specific_object,
        mainloop.cancellable,
        _active_connection_callback,
        user_data,
    )


def _active_connection_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        nm_act_con = src_object.activate_connection_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug(
                'Connection activation canceled on %s: error=%s',
                nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Connection activation failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    if nm_act_con is None:
        mainloop.quit('Connection activation failed on %s: error=unknown' %
                      nmdev.get_iface())
    else:
        devname = nm_act_con.props.connection.get_interface_name()
        logging.debug('Connection activation initiated: dev=%s, con-state=%s',
                      devname, nm_act_con.props.state)

        ac = ActiveConnection(nm_act_con)
        if ac.is_active:
            mainloop.execute_next_action()
        elif ac.is_activating:
            _waitfor_active_connection_async(ac, mainloop)
        else:
            mainloop.quit(
                'Connection activation failed on {}: reason={}'.format(
                    ac.devname, ac.reason))


def _waitfor_active_connection_async(ac, mainloop):
    ac.handlers.add(
        ac.nm_active_connection.connect(
            'state-changed', _waitfor_active_connection_callback, ac, mainloop)
    )


def _waitfor_active_connection_callback(
        nm_act_con, state, reason, ac, mainloop):
    ac.refresh_state()
    if ac.is_active:
        logging.debug('Connection activation succeeded: dev=%s, con-state=%s',
                      ac.devname, ac.state)
        for handler_id in ac.handlers:
            ac.nm_active_connection.handler_disconnect(handler_id)
        mainloop.execute_next_action()
    elif not ac.is_activating:
        for handler_id in ac.handlers:
            ac.nm_active_connection.handler_disconnect(handler_id)
        mainloop.quit('Connection activation failed on {}: reason={}'.format(
            ac.devname, ac.reason))


def deactivate(dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_deactivate_async, dev)


def _safe_deactivate_async(dev):
    act_connection = dev.get_active_connection()
    mainloop = nmclient.mainloop()
    if not act_connection or act_connection.props.state in (
            nmclient.NM.ActiveConnectionState.DEACTIVATING,
            nmclient.NM.ActiveConnectionState.DEACTIVATED):
        # Nothing left to do here, call the next action.
        mainloop.execute_next_action()
        return

    user_data = mainloop, dev
    client = nmclient.client()
    client.deactivate_connection_async(
        act_connection,
        mainloop.cancellable,
        _deactivate_connection_callback,
        user_data,
    )


def _deactivate_connection_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.deactivate_connection_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection deactivation aborted on %s: error=%s',
                          nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Connection deactivation failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    if success:
        logging.debug(
            'Connection deactivation succeeded on %s', nmdev.get_iface())
        mainloop.execute_next_action()
    else:
        mainloop.quit('Connection deactivation failed on %s: error=unknown' %
                      nmdev.get_iface())


def delete(dev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_async, dev)


def _safe_delete_async(dev):
    """Removes all device profiles."""
    connections = dev.get_available_connections()
    mainloop = nmclient.mainloop()
    if not connections:
        # No callback is expected, so we should call the next one.
        mainloop.execute_next_action()
        return

    user_data = mainloop, dev
    for con in connections:
        con.delete_async(
            mainloop.cancellable,
            _delete_connection_callback,
            user_data,
        )


def _delete_connection_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.delete_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Connection deletion aborted on %s: error=%s',
                          nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Connection deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    devname = src_object.get_interface_name()
    if success:
        logging.debug('Connection deletion succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Connection deletion failed: '
            'dev={}, error=unknown'.format(devname))


def get_device_by_name(devname):
    client = nmclient.client()
    return client.get_device_by_iface(devname)


def list_devices():
    client = nmclient.client(refresh=True)
    return client.get_devices()


def get_device_common_info(dev):
    return {
        'name': dev.get_iface(),
        'type_id': dev.get_device_type(),
        'type_name': dev.get_type_description(),
        'state': dev.get_state(),
    }


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
