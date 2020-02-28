#
# Copyright (c) 2020 Red Hat, Inc.
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

import datetime
import logging
from operator import itemgetter
import sys

from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateTimeoutError

from .common import NM
from .common import GLib
from .common import Gio

DEFAUL_TTIMEOUT = 35


class NmContext:
    def __init__(self):
        self._context = GLib.MainContext.new()
        self._context.acquire()
        self._context.push_thread_default()
        self._cli = NM.Client.new(cancellable=None)
        self._cancellable = Gio.Cancellable.new()
        self._quiting = False
        self._async_actions = {}
        self._error = None
        self._timeout_source = None

    @property
    def cancellable(self):
        return self._cancellable

    @property
    def client(self):
        if self._quiting:
            logging.error("BUG: Accessing NM.Client when it is cleaning up")
        return self._cli

    @property
    def context(self):
        if not self._context:
            raise NmstateInternalError(
                "BUG: Accessing MainContext while it is None"
            )
        return self._context

    def _del_client(self):
        if self._cli:
            ref_count = sys.getrefcount(self._cli)
            if ref_count > 2:
                logging.error(
                    "BUG: NM.Client reference is still hold by %d "
                    "process holding",
                    ref_count - 2,
                )
                self._cli = None
                return
            is_done = []
            self._cli.get_context_busy_watcher().weak_ref(
                lambda: is_done.append(1)
            )
            self._cli = None
            self._quiting = True

            while self.context.iteration(False):
                pass

            if not is_done:
                logging.debug(
                    "context.iteration() does not delete "
                    "the context_busy_watcher, "
                    "waiting 50 milliseconds"
                )
                timeout_source = GLib.timeout_source_new(50)
                try:
                    timeout_source.set_callback(lambda x: is_done.append(1))
                    timeout_source.attach(self.context)
                    while not is_done:
                        self.context.iteration(True)
                finally:
                    timeout_source.destroy()

    def _del_context(self):
        if self._context:
            self._context.release()
            self._context.pop_thread_default()
        self._context = None

    def __del__(self):
        if self._cancellable:
            self._cancellable.cancel()
            self._cancellable = None
        if self._timeout_source:
            self._timeout_source.destroy()
            self._timeout_source = None
        self._del_client()
        self._del_context()

    def register_async(self, action, timeout=DEFAUL_TTIMEOUT):
        """
        Register action(string) to wait list.
        """
        logging.debug(f"Async action: {action} started")
        self._async_actions[
            action
        ] = datetime.datetime.now() + datetime.timedelta(seconds=timeout)

    def finish_async(self, action, suppress_log=False):
        """
        Mark action(string) as finished.
        """
        if not suppress_log:
            logging.debug(f"Async action: {action} finished")
        self._async_actions.pop(action, None)

    def _remaining_timeout(self):
        """
        Return (action, remaining_timeout)
        """
        now = datetime.datetime.now()
        action, min_expire_time = min(
            self._async_actions.items(), key=itemgetter(1)
        )
        return action, min_expire_time - now

    def _action_all_finished(self):
        return len(self._async_actions) == 0

    def _timeout_cb(self, action):
        if not self._error:
            self.fail(NmstateTimeoutError(f"Action {action} timeout"))
        return GLib.SOURCE_REMOVE

    def fail(self, exception):
        if self._error:
            logging.error(
                f"BUG: There is already a exception assigned: "
                f"existing: {self._error}, new exception {exception}"
            )
        self.cancellable.cancel()
        self._error = exception

    def wait_all_finish(self):

        action, remaining_timeout = self._remaining_timeout()
        if remaining_timeout <= datetime.timedelta(seconds=0):
            self._timeout_cb(action)
        else:
            self._timeout_source = GLib.timeout_source_new(
                remaining_timeout.seconds * 1000
            )
            self._timeout_source.set_callback(self._timeout_cb, action)
            self._timeout_source.attach(self._context)

            while not self._action_all_finished() and not self._error:
                self.context.iteration(True)

        if self._error:
            raise self._error
