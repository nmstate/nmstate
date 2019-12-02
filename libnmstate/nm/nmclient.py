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
from collections import deque
from contextlib import contextmanager
import logging

import gi

try:
    gi.require_version('NM', '1.0')  # NOQA: F402
    from gi.repository import NM  # pylint: disable=no-name-in-module
except ValueError:
    NM = None

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject

from libnmstate import error

GObject

_mainloop = None
_nmclient = None

_can_disable_ipv6 = hasattr(NM, 'SETTING_IP6_CONFIG_METHOD_DISABLED')


def can_disable_ipv6():
    return _can_disable_ipv6


def nm_version():
    return NM.Client.get_version(client())


def client(refresh=False):
    global _nmclient
    # refresh is a workaround to get the current state when GMainLoop is not
    # running
    if _nmclient is None or refresh:
        if NM:
            _nmclient = NM.Client.new(None)
            if not _nmclient.get_nm_running():
                logging.error(
                    'NetworkManager is not running, please make sure'
                    'it is installed and running prior to running nmstate.\n'
                    'Check the documentation for more information.'
                )
                raise error.NmstateDependencyError(
                    'NetworkManager is not running'
                )
        else:
            logging.error(
                'Missing introspection data for libnm'
                'please make sure to install it prior to running nmstate.\n'
                'Check the documentation for more information.'
            )
            raise error.NmstateDependencyError(
                'Missing introspection data for libnm'
            )
    return _nmclient


def mainloop(refresh=False):
    """
    Create a singleton (global) mainloop object.

    When the refresh flag is set, the existing mainloop object is re-created.
    Use the refresh flag in scenarios where the mainloop is needed but
    the existing object is no longer usable (in an undefined state),
    e.g. the mainloop exited with failure.
    """
    global _mainloop
    if _mainloop is None or refresh:
        _mainloop = _MainLoop()
    return _mainloop


class _MainLoop:
    SUCCESS = True
    FAIL = False
    RUN_TIMEOUT_ERROR = 'run timeout'
    RUN_EXECUTION_ERROR = 'run execution'

    def __init__(self):
        self._action_queue = deque()
        self._mainloop = GLib.MainLoop()
        self._cancellables = []
        self.new_cancellable()
        self._error = ''

    def execute_next_action(self):
        action = self.pop_action()
        if action:
            func, args, kwargs = action
            logging.debug('Executing NM action: func=%s', func.__name__)
            func(*args, **kwargs)
        else:
            logging.debug('NM action queue exhausted, quiting mainloop')
            self._mainloop.quit()

    def push_action(self, func, *args, **kwargs):
        action = (func, args, kwargs)
        self._action_queue.append(action)

    def pop_action(self):
        try:
            action = self._action_queue.popleft()
        except IndexError:
            return None

        return action if action[0] else None

    def actions_exists(self):
        return bool(self._action_queue)

    def run(self, timeout):
        if not isinstance(timeout, int):
            raise error.NmstateValueError(
                "Invalid timeout value: should be an integer"
            )

        if not self.actions_exists():
            return _MainLoop.SUCCESS

        with self._idle_timeout(timeout):
            self._register_first_action()
            self._mainloop.run()

        if self._error == _MainLoop.RUN_TIMEOUT_ERROR:
            return _MainLoop.FAIL

        if len(self._action_queue):
            self._error = _MainLoop.RUN_EXECUTION_ERROR
            return _MainLoop.FAIL

        return _MainLoop.SUCCESS

    @property
    def cancellable(self):
        return self._cancellables[0]

    def new_cancellable(self):
        c = Gio.Cancellable.new()
        self._cancellables.append(c)
        return c

    def drop_cancellable(self, c):
        idx = self._cancellables.index(c)
        if idx == 0:
            raise error.NmstateInternalError('Cannot drop main cancellable')
        del self._cancellables[idx]

    def _cancel_cancellables(self):
        for c in self._cancellables:
            c.cancel()

    def quit(self, reason):
        logging.error('NM main-loop aborted: %s', reason)
        # In case it was the last action, add a sentinel to fail run.
        self.push_action(None)
        self._mainloop.quit()
        self._cancel_cancellables()

    def is_action_canceled(self, err):
        return (
            isinstance(err, GLib.GError)
            and err.domain == 'g-io-error-quark'
            and err.code == Gio.IOErrorEnum.CANCELLED
        )

    @property
    def error(self):
        return self._error

    @contextmanager
    def _idle_timeout(self, timeout):
        timeout_result = []
        data = (self._mainloop, timeout_result)
        timeout_id = GLib.timeout_add(
            int(timeout * 1000), _MainLoop._timeout_cb, data
        )
        yield
        if timeout_result:
            self._cancel_cancellables()
            self._error = _MainLoop.RUN_TIMEOUT_ERROR
        else:
            GLib.source_remove(timeout_id)

    @staticmethod
    def _timeout_cb(data):
        mainloop, result = data
        result.append(1)
        logging.warning('NM main-loop timed out.')
        mainloop.quit()
        return _MainLoop.FAIL

    def _register_first_action(self):
        GLib.timeout_add(1, self._execute_action_once, None)

    def _execute_action_once(self, _):
        self.execute_next_action()
        return False
