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

from contextlib import contextmanager
import logging

from libnmstate.nm import nmclient


class NMCheckPointError(Exception):
    pass


class NMCheckPointCreationError(NMCheckPointError):
    pass


class NMCheckPointPermissionError(NMCheckPointError):
    pass


def get_checkpoints():
    nmclient = libnmstate.nm.nmclient.client(refresh=True)

    return [c.get_path() for c in nmclient.get_checkpoints()]


class CheckPoint(object):
    def __init__(self, timeout=60, autodestroy=True, dbuspath=None):
        self._timeout = timeout
        self._autodestroy = autodestroy
        self._dbuspath = dbuspath
        self._mainloop = nmclient.mainloop(refresh=True)
        self._nmclient = nmclient.client()

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
        cp_flags = (
            nmclient.NM.CheckpointCreateFlags.DELETE_NEW_CONNECTIONS
            | nmclient.NM.CheckpointCreateFlags.DISCONNECT_NEW_DEVICES
        )
        userdata = self
        devs = []

        self._mainloop.push_action(
            self._nmclient.checkpoint_create,
            devs,
            self._timeout,
            cp_flags,
            self._mainloop.cancellable,
            CheckPoint._checkpoint_create_callback,
            userdata,
        )

        ok = self._mainloop.run(self._timeout)
        if not ok:
            raise NMCheckPointCreationError(
                'Failed to create checkpoint: '
                '{}'.format(self._mainloop.error)
            )

    def destroy(self):
        if self._dbuspath:
            dbus_path = self._dbuspath
            userdata = self
            self._mainloop.push_action(
                self._nmclient.checkpoint_destroy,
                self._dbuspath,
                self._mainloop.cancellable,
                CheckPoint._checkpoint_destroy_callback,
                userdata,
            )
            ok = self._mainloop.run(self._timeout)
            if not ok:
                raise NMCheckPointError(
                    'Failed to destroy checkpoint {}: '
                    '{}'.format(self._dbuspath, self._mainloop.error)
                )
            logging.debug('Checkpoint %s destroyed', dbus_path)
        else:
            raise NMCheckPointError('No checkpoint to destroy')

    def rollback(self):
        if self._dbuspath:
            dbus_path = self._dbuspath
            userdata = self
            self._mainloop.push_action(
                self._nmclient.checkpoint_rollback,
                dbus_path,
                self._mainloop.cancellable,
                CheckPoint._checkpoint_rollback_callback,
                userdata,
            )
            ok = self._mainloop.run(self._timeout)
            if not ok:
                raise NMCheckPointError(
                    'Failed to rollback checkpoint {}: {}'.format(
                        self._dbuspath, self._mainloop.error
                    )
                )
            logging.debug('Checkpoint %s rollback executed', dbus_path)
        else:
            raise NMCheckPointError('No checkpoint to rollback')

        return

    @property
    def dbuspath(self):
        return self._dbuspath

    @staticmethod
    def _checkpoint_create_callback(client, result, data):
        checkpoint = data
        mainloop = checkpoint._mainloop
        try:
            cp = client.checkpoint_create_finish(result)
            checkpoint._dbuspath = cp.get_path()
            if cp:
                logging.debug(
                    'Checkpoint {} created for all devices'.format(
                        checkpoint._dbuspath
                    )
                )
                mainloop.execute_next_action()
            else:
                mainloop.quit(
                    'Checkpoint creation failed: error={}'.format(
                        mainloop.error
                    )
                )
        except Exception as e:
            if mainloop.is_action_canceled(e):
                logging.debug(
                    'Checkpoint creation canceled: error={}'.format(e)
                )
            else:
                mainloop.quit('Checkpoint creation failed: error={}'.format(e))

    @staticmethod
    def _checkpoint_rollback_callback(client, result, data):
        checkpoint = data
        mainloop = checkpoint._mainloop
        try:
            CheckPoint._check_rollback_result(
                client, result, checkpoint._dbuspath
            )
            checkpoint._dbuspath = None
            mainloop.execute_next_action()
        except Exception as e:
            if mainloop.is_action_canceled(e):
                logging.debug(
                    'Checkpoint rollback canceled: error={}'.format(e)
                )
            else:
                mainloop.quit('Checkpoint rollback failed: error={}'.format(e))

    @staticmethod
    def _check_rollback_result(client, result, dbus_path):
        ret = client.checkpoint_rollback_finish(result)
        logging.debug('Checkpoint %s rollback executed', dbus_path)
        for path in ret:
            d = client.get_device_by_path(path)
            iface = path if d is None else d.get_iface()
            if ret[path] != 0:
                logging.error('Interface %s rollback failed', iface)
            else:
                logging.debug('Interface %s rollback succeeded', iface)

    @staticmethod
    def _checkpoint_destroy_callback(client, result, data):
        checkpoint = data
        mainloop = checkpoint._mainloop
        try:
            client.checkpoint_destroy_finish(result)
            logging.debug(
                'Checkpoint %s destroy executed', checkpoint._dbuspath
            )
            checkpoint._dbuspath = None
            mainloop.execute_next_action()
        except Exception as e:
            if mainloop.is_action_canceled(e):
                logging.debug(
                    'Checkpoint %s destroy canceled: error=%s',
                    checkpoint._dbuspath,
                    e,
                )
            else:
                mainloop.quit(
                    'Checkpoint {} destroy failed: error={}'.format(
                        checkpoint._dbuspath, e
                    )
                )
