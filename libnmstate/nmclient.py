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
import logging

try:
    import gi                           # pylint: disable=import-error
    gi.require_version('NM', '1.0')     # NOQA: F402
    from gi.repository import Gio, GLib, NM  # pylint: disable=import-error
except ImportError:
    # Allow the error to pass in case we are running in a unit test context
    g = None
    Gio = None
    GLib = None
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

    def __init__(self):
        self._action_queue = deque()
        self._mainloop = GLib.MainLoop()
        self._cancellable = Gio.Cancellable.new()
        self._error = ''

    def execute_next_action(self):
        action = self.pop_action()
        if action:
            func, args, kwargs = action
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
        if timeout is None:
            self._mainloop.run()
            return _MainLoop.SUCCESS

        timeout_result = []
        data = (self._mainloop, timeout_result)
        timeout_id = GLib.timeout_add(
            int(timeout * 1000),
            _MainLoop._timeout_cb,
            data
        )
        self._mainloop.run()

        if timeout_result:
            self._cancellable.cancel()
            self._error = 'run timeout'
            return _MainLoop.FAIL

        GLib.source_remove(timeout_id)

        if len(self._action_queue):
            self._error = 'run execution'
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

    @staticmethod
    def _timeout_cb(data):
        mainloop, result = data
        result.append(1)
        logging.warning('NM main-loop timed out.')
        mainloop.quit()
        return _MainLoop.FAIL
