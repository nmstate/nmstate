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

try:
    import dbus                         # pylint: disable=import-error
except ImportError:
    # dbus is set to None to indicate that checkpoint is not available
    dbus = None


DBUS_STD_PROPERTIES_IFNAME = 'org.freedesktop.DBus.Properties'
CHECKPOINT_CREATE_FLAG_DESTROY_ALL = 0x01
CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS = 0x02
CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES = 0x04

_nmdbus_manager = None


def has_checkpoint_capability():
    return dbus is not None


def nmdbus_manager():
    """
    Returns the NM manager.
    If it does not exists, it will initialize the dbus connection and
    create the manager.
    """
    global _nmdbus_manager
    if _nmdbus_manager is None:
        _NMDbus.init()
        _nmdbus_manager = _NMDbusManager()
    return _nmdbus_manager


class _NMDbus(object):
    BUS_NAME = 'org.freedesktop.NetworkManager'

    bus = None

    @staticmethod
    def init():
        _NMDbus.bus = dbus.SystemBus()


class _NMDbusManager(object):
    IF_NAME = 'org.freedesktop.NetworkManager'
    OBJ_PATH = '/org/freedesktop/NetworkManager'

    def __init__(self):
        mng_proxy = _NMDbus.bus.get_object(_NMDbus.BUS_NAME,
                                           _NMDbusManager.OBJ_PATH)
        self.properties = dbus.Interface(mng_proxy, DBUS_STD_PROPERTIES_IFNAME)
        self.interface = dbus.Interface(mng_proxy, _NMDbusManager.IF_NAME)


class CheckPoint(object):

    def __init__(self, timeout=60):
        self._manager = nmdbus_manager()
        self._timeout = timeout
        self._checkpoint = None

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # If the rollback has been explicit or implicit triggered already,
            # this command should fail.
            self.destroy()
        else:
            self.rollback()
            raise

    def create(self):
        devs = []
        timeout = self._timeout
        cp_flags = (
            CHECKPOINT_CREATE_FLAG_DESTROY_ALL |
            CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS |
            CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES
        )
        cp = self._manager.interface.CheckpointCreate(devs, timeout, cp_flags)
        logging.debug('Checkpoint %s created for all devices: %s', cp, timeout)
        self._checkpoint = cp

    def destroy(self):
        self._manager.interface.CheckpointDestroy(self._checkpoint)
        logging.debug('Checkpoint %s destroyed', self._checkpoint)

    def rollback(self):
        result = self._manager.interface.CheckpointRollback(self._checkpoint)
        logging.debug('Checkpoint %s rollback executed: %s',
                      self._checkpoint, result)
        return result
