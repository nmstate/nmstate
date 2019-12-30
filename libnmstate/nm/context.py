# Copyright (c) 2019 Red Hat, Inc.
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
from distutils.version import StrictVersion
import logging

from libnmstate.error import NmstateDependencyError
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateInternalError
from libnmstate.nm.nmclient import GLib
from libnmstate.nm.nmclient import Gio
from libnmstate.nm.nmclient import NM
from libnmstate.nm.nmclient import nm_version

_NMCLIENT_CLEANUP_TIMEOUT = 5


class NmContext:
    def __init__(self):
        if NM is None:
            raise NmstateDependencyError("The libnm is not installed")
        self._nmclient = NM.Client.new(None)
        self._mainloop = _MainLoop()
        self._can_disable_ipv6 = hasattr(
            NM, "SETTING_IP6_CONFIG_METHOD_DISABLED"
        )
        logging.debug("NM.Client and GLib.MainLoop created")

    @property
    def client(self):
        return self._nmclient

    @property
    def mainloop(self):
        return self._mainloop

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        if nm_version(self.client) >= StrictVersion("1.21.0"):
            self._nmclient_cleanup()
        else:
            self._nmclient_cleanup_old()

    def _nmclient_cleanup_old(self):
        self._nmclient = None
        self._mainloop = None

    def _nmclient_cleanup(self):
        if self.client and self.mainloop:
            context_busy_watcher = self.client.get_context_busy_watcher()
            self.mainloop.push_action(
                self._wait_nmclient_unref, context_busy_watcher
            )
            del context_busy_watcher
            self._nmclient = None
            self.mainloop.run(_NMCLIENT_CLEANUP_TIMEOUT)

    def _wait_nmclient_unref(self, context_busy_watcher):
        context_busy_watcher.weak_ref(self._busy_watcher_destruct_callback)

    def _busy_watcher_destruct_callback(self):
        self.mainloop.execute_next_action()
        self._mainloop = None
        logging.debug("NM.Client and GLib.MainLoop cleaned")


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
            logging.debug("NM action queue exhausted, quiting mainloop")
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
            raise NmstateValueError(
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
            self._action_queue = deque()
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
            raise NmstateInternalError("Cannot drop main cancellable")
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

    def _register_first_action(self):
        GLib.timeout_add(1, self._execute_action_once, None)

    def _execute_action_once(self, _):
        self.execute_next_action()
        return False
