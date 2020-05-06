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
from collections import deque
from contextlib import contextmanager
import logging

from libnmstate import error

from .common import GLib
from .common import Gio

_mainloop = None


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
    RUN_TIMEOUT_ERROR = "run timeout"
    RUN_EXECUTION_ERROR = "run execution"

    def __init__(self):
        self._action_queue = deque()
        self._mainloop = GLib.MainLoop()
        self._cancellables = []
        self.new_cancellable()
        self._error = ""

    def execute_next_action(self):
        action = self.pop_action()
        if action:
            func, args, kwargs = action
            logging.debug("Executing NM action: func=%s", func.__name__)
            func(*args, **kwargs)
        else:
            logging.debug("NM action queue exhausted, quitting mainloop")
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
            return

        self._register_first_action(timeout)
        self._mainloop.run()

        if self._error == _MainLoop.RUN_TIMEOUT_ERROR:
            raise error.NmstateTimeoutError(
                f"libnm mainloop timed out after {timeout} seconds."
            )

        if len(self._action_queue):
            err = _MainLoop.RUN_EXECUTION_ERROR
            raise error.NmstateLibnmError(
                f"Unexpected failure of libnm when running the mainloop: {err}"
            )

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
            raise error.NmstateInternalError("Cannot drop main cancellable")
        del self._cancellables[idx]

    def _cancel_cancellables(self):
        for c in self._cancellables:
            c.cancel()

    def quit(self, reason):
        logging.error("NM main-loop aborted: %s", reason)
        # In case it was the last action, add a sentinel to fail run.
        self.push_action(None)
        self._mainloop.quit()
        self._cancel_cancellables()

    def is_action_canceled(self, err):
        return (
            isinstance(err, GLib.GError)
            and err.domain == "g-io-error-quark"
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
        logging.warning("NM main-loop timed out.")
        mainloop.quit()
        return _MainLoop.FAIL

    def _register_first_action(self, timeout):
        GLib.timeout_add(1, self._execute_action_once, timeout)

    def _execute_action_once(self, timeout):
        with self._idle_timeout(timeout):
            self.execute_next_action()
        return False
