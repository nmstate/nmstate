#
# Copyright (c) 2018-2019 Red Hat, Inc.
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

from . import active_connection as ac
from . import connection
from . import nmclient

from distutils.version import StrictVersion


def activate(dev=None, connection_id=None):
    """Activate the given device or remote connection profile."""
    conn = connection.ConnectionProfile()
    conn.nmdevice = dev
    conn.con_id = connection_id
    conn.activate()


def deactivate(dev):
    """
    Deactivating the current active connection,
    The profile itself is not removed.

    For software devices, deactivation removes the devices from the kernel.
    """
    act_con = ac.ActiveConnection()
    act_con.nmdevice = dev
    act_con.deactivate()


def delete(dev):
    connections = dev.get_available_connections()
    for con in connections:
        con_profile = connection.ConnectionProfile(con)
        con_profile.delete()


def reapply(dev, connection_profile):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_reapply_async, dev, connection_profile)


def _safe_reapply_async(dev, connection_profile):
    mainloop = nmclient.mainloop()
    cancellable = mainloop.new_cancellable()

    if _wait_for_active_connection_async(dev, connection_profile):
        return

    version_id = 0
    flags = 0
    user_data = mainloop, dev, cancellable
    dev.reapply_async(
        connection_profile,
        version_id,
        flags,
        cancellable,
        _reapply_callback,
        user_data,
    )


def _wait_for_active_connection_async(dev, connection_profile):
    active_conn = connection.get_device_active_connection(dev)
    if active_conn:
        act_conn = ac.ActiveConnection(active_conn)
        if act_conn.is_activating:
            logging.debug(
                'Connection activation in progress: dev=%s, state=%s',
                act_conn.devname,
                act_conn.state,
            )
            conn = connection.ConnectionProfile(connection_profile)
            conn.waitfor_active_connection_async(act_conn)
            return True
    return False


def _reapply_callback(src_object, result, user_data):
    mainloop, nmdev, cancellable = user_data
    mainloop.drop_cancellable(cancellable)

    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Device reapply aborted on %s: error=%s', devname, e)
        else:
            mainloop.quit(
                'Device reapply failed on {}: error={}'.format(devname, e)
            )
        return

    if success:
        logging.debug('Device reapply succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Device reapply failed: dev={}, error=unknown'.format(devname)
        )


def modify(dev, connection_profile):
    """
    Modify the given connection profile on the device.
    Implemented by the reapply operation with a fallback to the
    connection profile activation.
    """
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_modify_async, dev, connection_profile)


def _safe_modify_async(dev, connection_profile):
    # Special cases are known to exist (bugs) where reapply is not functioning
    # correctly. Use activation instead. (https://bugzilla.redhat.com/1702657)
    if _requires_activation(dev, connection_profile):
        _activate_async(dev)
        return

    mainloop = nmclient.mainloop()
    cancellable = mainloop.new_cancellable()

    if _wait_for_active_connection_async(dev, connection_profile):
        return

    version_id = 0
    flags = 0
    user_data = mainloop, dev, cancellable
    dev.reapply_async(
        connection_profile,
        version_id,
        flags,
        cancellable,
        _modify_callback,
        user_data,
    )


def _modify_callback(src_object, result, user_data):
    mainloop, nmdev, cancellable = user_data
    mainloop.drop_cancellable(cancellable)

    devname = src_object.get_iface()
    try:
        success = src_object.reapply_finish(result)
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug('Device reapply aborted on %s: error=%s', devname, e)
        else:
            logging.debug(
                'Device reapply failed on %s: error=%s\n'
                'Fallback to device activation',
                devname,
                e,
            )
            _activate_async(src_object)
        return

    if success:
        logging.debug('Device reapply succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        logging.debug(
            'Device reapply failed, fallback to device activation: dev=%s, '
            'error=unknown',
            devname,
        )
        _activate_async(src_object)


def _requires_activation(dev, connection_profile):
    if StrictVersion(nmclient.nm_version()) < StrictVersion(
        '1.18'
    ) and _mtu_changed(dev, connection_profile):
        logging.debug(
            'Device reapply does not support mtu changes, '
            'fallback to device activation: dev=%s',
            dev.get_iface(),
        )
        return True
    if _ipv6_changed(dev, connection_profile):
        logging.debug(
            'Device reapply does not support ipv6 changes, '
            'fallback to device activation: dev=%s',
            dev.get_iface(),
        )
        return True
    return False


def _mtu_changed(dev, connection_profile):
    wired_setting = connection_profile.get_setting_wired()
    configured_mtu = wired_setting.props.mtu if wired_setting else None
    if configured_mtu:
        current_mtu = int(dev.get_mtu())
        return configured_mtu != current_mtu
    return False


def _ipv6_changed(dev, connection_profile):
    """
    Detecting that the IPv6 method changed is not possible at this stage,
    therefore, if IPv6 is defined (i.e. the method if not 'ignore' or
    'disabled'), IPv6 is considered as changed.
    """
    ipv6_setting = connection_profile.get_setting_ip6_config()
    if ipv6_setting:
        methods = [nmclient.NM.SETTING_IP6_CONFIG_METHOD_IGNORE]
        if nmclient.can_disable_ipv6():
            # pylint: disable=no-member
            methods.append(nmclient.NM.SETTING_IP6_CONFIG_METHOD_DISABLED)
            # pylint: enable=no-member
        return ipv6_setting.props.method not in methods
    return False


def _activate_async(dev):
    conn = connection.ConnectionProfile()
    conn.nmdevice = dev
    if dev:
        # Workaround of https://bugzilla.redhat.com/show_bug.cgi?id=1772470
        dev.set_managed(True)
    conn.safe_activate_async()


def delete_device(nmdev):
    mainloop = nmclient.mainloop()
    mainloop.push_action(_safe_delete_device_async, nmdev)


def _safe_delete_device_async(nmdev):
    mainloop = nmclient.mainloop()
    user_data = mainloop, nmdev
    nmdev.delete_async(
        mainloop.cancellable, _delete_device_callback, user_data
    )


def _delete_device_callback(src_object, result, user_data):
    mainloop, nmdev = user_data
    try:
        success = src_object.delete_finish(result)
    # pylint: disable=catching-non-exception
    except nmclient.GLib.GError as e:
        # pylint: enable=catching-non-exception
        if e.matches(
            nmclient.Gio.DBusError.quark(),
            nmclient.Gio.DBusError.UNKNOWN_METHOD,
        ) or (
            e.matches(
                nmclient.NM.DeviceError.quark(),
                nmclient.NM.DeviceError.NOTSOFTWARE,
            )
            and nmdev.is_software()
        ):
            logging.debug(
                'Device %s has been already deleted: error=%s',
                nmdev.get_iface(),
                e,
            )
            mainloop.execute_next_action()
        else:
            mainloop.quit(
                'Device deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e
                )
            )
        return
    except Exception as e:
        if mainloop.is_action_canceled(e):
            logging.debug(
                'Device deletion aborted on %s: error=%s', nmdev.get_iface(), e
            )
        else:
            mainloop.quit(
                'Device deletion failed on {}: error={}'.format(
                    nmdev.get_iface(), e
                )
            )
        return

    devname = src_object.get_iface()
    if success:
        logging.debug('Device deletion succeeded: dev=%s', devname)
        mainloop.execute_next_action()
    else:
        mainloop.quit(
            'Device deletion failed: dev={}, error=unknown'.format(devname)
        )


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
