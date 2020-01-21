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

import logging

import dbus

from libnmstate.nm.nmclient import nmclient_context
from libnmstate.nm.nmclient import client


DBUS_STD_PROPERTIES_IFNAME = "org.freedesktop.DBus.Properties"

CHECKPOINT_CREATE_FLAG_DESTROY_ALL = 0x01
CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS = 0x02
CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES = 0x04

NM_PERMISSION_DENIED = "org.freedesktop.NetworkManager.PermissionDenied"


class NMCheckPointError(Exception):
    pass


class NMCheckPointCreationError(NMCheckPointError):
    pass


class NMCheckPointPermissionError(NMCheckPointError):
    pass


def nmdbus_manager():
    """
    Returns the NM manager.
    Initializes the dbus connection and creates the manager.
    """
    _NMDbus.init()
    return _NMDbusManager()


class _NMDbus:
    BUS_NAME = "org.freedesktop.NetworkManager"

    bus = None

    @staticmethod
    def init():
        _NMDbus.bus = dbus.SystemBus()


class _NMDbusManager:
    IF_NAME = "org.freedesktop.NetworkManager"
    OBJ_PATH = "/org/freedesktop/NetworkManager"

    def __init__(self):
        mng_proxy = _NMDbus.bus.get_object(
            _NMDbus.BUS_NAME, _NMDbusManager.OBJ_PATH
        )
        self.properties = dbus.Interface(mng_proxy, DBUS_STD_PROPERTIES_IFNAME)
        self.interface = dbus.Interface(mng_proxy, _NMDbusManager.IF_NAME)


@nmclient_context
def get_checkpoints():
    nm_client = client()
    checkpoints = [c.get_path() for c in nm_client.get_checkpoints()]
    return checkpoints


class CheckPoint:
    def __init__(self, timeout=60, autodestroy=True, dbuspath=None):
        self._manager = nmdbus_manager()
        self._timeout = timeout
        self._dbuspath = dbuspath
        self._autodestroy = autodestroy

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            if self._autodestroy:
                # If the rollback has been explicit or implicit triggered
                # already, this command should fail.
                self.destroy()
        else:
            self.rollback()

    def create(self):
        devs = []
        timeout = self._timeout
        cp_flags = (
            CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS
            | CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES
        )
        try:
            dbuspath = self._manager.interface.CheckpointCreate(
                devs, timeout, cp_flags
            )
            logging.debug(
                "Checkpoint %s created for all devices: %s", dbuspath, timeout
            )
            self._dbuspath = dbuspath
        except dbus.exceptions.DBusException as e:
            if e.get_dbus_name() == NM_PERMISSION_DENIED:
                raise NMCheckPointPermissionError(str(e))
            raise NMCheckPointCreationError(str(e))

    def destroy(self):
        try:
            self._manager.interface.CheckpointDestroy(self._dbuspath)
        except dbus.exceptions.DBusException as e:
            raise NMCheckPointError(str(e))

        logging.debug("Checkpoint %s destroyed", self._dbuspath)

    def rollback(self):
        try:
            result = self._manager.interface.CheckpointRollback(self._dbuspath)
        except dbus.exceptions.DBusException as e:
            raise NMCheckPointError(str(e))
        logging.debug(
            "Checkpoint %s rollback executed: %s", self._dbuspath, result
        )
        return result

    @property
    def dbuspath(self):
        return self._dbuspath
