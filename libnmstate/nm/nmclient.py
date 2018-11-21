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
from __future__ import absolute_import

from collections import deque
from contextlib import contextmanager
import logging

import six

try:
    import gi                           # pylint: disable=import-error
    gi.require_version('NM', '1.0')     # NOQA: F402
    from gi.repository import Gio, GLib, NM  # pylint: disable=import-error
    from gi.repository import GObject        # pylint: disable=import-error
except ImportError:
    # Allow the error to pass in case we are running in a unit test context
    g = None
    Gio = None
    GLib = None
    GObject = None
    NM = None


_mainloop = None
_nmclient = None


def client(refresh=False):
    global _nmclient
    # refresh is a workaround to get the current state when GMainLoop is not
    # running
    if _nmclient is None or refresh:
        _nmclient = NM.Client.new(None)
    return _nmclient


def mainloop():
    global _mainloop
    if _mainloop is None:
        _mainloop = _MainLoop()
    return _mainloop


class _MainLoop(object):
    SUCCESS = True
    FAIL = False
    RUN_TIMEOUT_ERROR = 'run timeout'
    RUN_EXECUTION_ERROR = 'run execution'

    def __init__(self):
        self._action_queue = deque()
        self._mainloop = GLib.MainLoop()
        self._cancellable = Gio.Cancellable.new()
        self._error = ''

    def execute_next_action(self):
        action = self.pop_action()
        if action:
            func, args, kwargs = action
            logging.debug('Executing NM action: func=%s, args=%s',
                          func.__name__, args)
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
        if not isinstance(timeout, six.integer_types):
            raise TypeError('timeout is expected to be an integer')

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
        return self._cancellable

    def quit(self, reason):
        logging.error('NM main-loop aborted: %s', reason)
        # In case it was the last action, add a sentinel to fail run.
        self.push_action(None)
        self._mainloop.quit()
        self._cancellable.cancel()

    def is_action_canceled(self, err):
        return (isinstance(err, GLib.GError) and
                err.domain == 'g-io-error-quark' and
                err.code == Gio.IOErrorEnum.CANCELLED)

    @property
    def error(self):
        return self._error

    @contextmanager
    def _idle_timeout(self, timeout):
        timeout_result = []
        data = (self._mainloop, timeout_result)
        timeout_id = GLib.timeout_add(
            int(timeout * 1000),
            _MainLoop._timeout_cb,
            data
        )
        yield
        if timeout_result:
            self._cancellable.cancel()
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
