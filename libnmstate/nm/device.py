#
# Copyright 2018-2019 Red Hat, Inc.
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

from . import connection
from . import nmclient


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
    def state(self):
        return self._state

    @property
    def nmdev_state(self):
        return (self._nmdev.get_state() if self._nmdev
                else nmclient.NM.DeviceState.UNKNOWN)


def activate(dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    mainloop = nmclient.mainloop()
    mainloop.push_action(
        _safe_activate_async, dev, connection_id)


def _safe_activate_async(dev, connection_id):
    client = nmclient.client()
    mainloop = nmclient.mainloop()
    cancellable = mainloop.new_cancellable()

    conn = connection.get_connection_by_id(connection_id)
    if conn:
        dev = None
    active_conn = connection.get_device_active_connection(dev)
    if active_conn:
        ac = ActiveConnection(active_conn)
        if ac.is_activating:
            logging.debug(
                'Connection activation in progress: dev=%s, state=%s',
                ac.devname, ac.state)
            _waitfor_active_connection_async(ac, mainloop)
            return

    specific_object = None
    user_data = mainloop, dev, connection_id, cancellable
    client.activate_connection_async(
        conn,
        dev,
        specific_object,
        cancellable,
        _active_connection_callback,
        user_data,
    )


def _active_connection_callback(src_object, result, user_data):
    mainloop, nmdev, connection_id, cancellable = user_data
    mainloop.drop_cancellable(cancellable)

    try:
        nm_act_con = src_object.activate_connection_finish(result)
    except Exception as e:
        activation_type, activation_object = _get_activation_metadata(
            nmdev, connection_id)

        if mainloop.is_action_canceled(e):
            logging.debug(
                'Connection activation canceled on %s %s: error=%s',
                activation_type, activation_object, e)
        elif is_connection_unavailable(e):
            logging.warning('Connection unavailable on %s %s, retrying',
                            activation_type, activation_object)
            mainloop.execute_last_action()
        else:
            mainloop.quit(
                'Connection activation failed on {} {}: error={}'.format(
                    activation_type, activation_object, e))
        return

    if nm_act_con is None:
        activation_type, activation_object = _get_activation_metadata(
            nmdev, connection_id)
        mainloop.quit('Connection activation failed on %s %s: error=unknown' %
                      activation_type, activation_object)
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


def is_connection_unavailable(err):
    return (isinstance(err, nmclient.GLib.GError) and
            err.domain == 'nm-manager-error-quark' and
            err.code == 2 and
            'is not available on the device' in err.message)


def _get_activation_metadata(nmdev, connection_id):
    if nmdev:
        activation_type = 'device'
        activation_object = nmdev.get_iface()
    elif connection_id:
        activation_type = 'connection_id'
        activation_object = connection_id
    else:
        activation_type = activation_object = 'unknown'

    return activation_type, activation_object


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


# FIXME: Move the connection related functionality to the connection module.
def delete_connection(connection_id):
    mainloop = nmclient.mainloop()
    mainloop.push_action(
        _safe_delete_async, dev=None, connection_id=connection_id)


def _safe_delete_async(dev, connection_id=None):
    """Removes all device profiles."""
    if dev:
        connections = dev.get_available_connections()
        if not connections:
            con = connection.get_connection_by_id(dev.get_iface())
            if con:
                connections = [con]
    else:
        conn = connection.get_connection_by_id(connection_id)
        connections = [conn] if conn else []
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


def delete_device(nmdev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_device_async, nmdev)


def _safe_delete_device_async(nmdev):
    mainloop = nmclient.mainloop()
    if nmdev.get_state() == nmclient.NM.DeviceState.DEACTIVATING:
        # Nothing to do since the device is already being removed.
        mainloop.execute_next_action()
        return

    user_data = mainloop, nmdev
    nmdev.delete_async(
        mainloop.cancellable,
        _delete_device_callback,
        user_data,
    )


def _delete_device_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.delete_finish(result)
    # pylint: disable=catching-non-exception
    except nmclient.GLib.GError as e:
        # pylint: enable=catching-non-exception
        if e.matches(nmclient.Gio.DBusError.quark(),
                     nmclient.Gio.DBusError.UNKNOWN_METHOD):
            logging.debug('Device %s has been already deleted: error=%s',
                          nmdev.get_iface(), e)
            mainloop.execute_next_action()
        else:
            mainloop.quit(
                'Device deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Device deletion aborted on %s: error=%s',
                          nmdev.get_iface(), e)
        else:
            mainloop.quit(
                'Device deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e))
        return

    devname = src_object.get_iface()
    if success:
        logging.debug('Device deletion succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Device deletion failed: dev={}, error=unknown'.format(devname))


def get_device_by_name(devname):
    client = nmclient.client()
    return client.get_device_by_iface(devname)


def list_devices():
    client = nmclient.client()
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
