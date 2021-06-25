#
# Copyright (c) 2020-2021 Red Hat, Inc.
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

from libnmstate.error import NmstateInternalError
from libnmstate.error import NmstateTimeoutError

from .common import NM
from .common import GLib
from .common import Gio

# Interval for idle checker to check on whether timeout should trigger since
# last finish async action.
IDLE_CHECK_INTERNAL = 5

IDLE_TIMEOUT = 60 * 5  # 5 minitues

# NetworkManage is using dbus in libnm while the dbus has limitation on
# maximum number of pending replies per connection.(RHEL/CentOS 8 is 1024)
# Hence limit the synchronous queue size
SLOW_ASYNC_QUEUE_SIZE = 100
FAST_ASYNC_QUEUE_SIZE = 300


class NmContext:
    def __init__(self):
        self._client = NM.Client.new(cancellable=None)
        self._context = self._client.get_main_context()
        self._quitting = False
        self._cancellable = None
        self._error = None
        self._timeout_source = None
        self._last_async_finish_time = None
        self._fast_queue = None
        self._slow_queue = None
        self._init_queue()
        self._init_cancellable()

    def _init_client(self):
        self._client = NM.Client.new(cancellable=None)
        self._context = self._client.get_main_context()

    def _init_queue(self):
        self._fast_queue = set()
        self._slow_queue = set()

    def _init_cancellable(self):
        self._cancellable = Gio.Cancellable.new()

    @property
    def cancellable(self):
        return self._cancellable

    def refresh(self):
        while self.context.iteration(False):
            pass

    @property
    def client(self):
        if self._quitting:
            return None
        return self._client

    @property
    def context(self):
        if not self._context:
            raise NmstateInternalError(
                "BUG: Accessing MainContext while it is None"
            )
        return self._context

    def clean_up(self):
        if self._cancellable:
            self._cancellable.cancel()
        self._del_timeout()
        self._del_client()
        self._context = None
        self._cancellable = None

    def _del_client(self):
        if self._client:
            is_done = []
            is_timeout = []
            self._client.get_context_busy_watcher().weak_ref(
                lambda: is_done.append(1)
            )
            self._client = None
            self._quitting = True

            if not is_done:
                timeout_source = GLib.timeout_source_new(50)
                try:
                    timeout_source.set_callback(lambda x: is_timeout.append(1))
                    timeout_source.attach(self.context)
                    while not is_done and not is_timeout:
                        self.context.iteration(True)
                finally:
                    timeout_source.destroy()
            if not is_done:
                logging.error("BUG: NM.Client is not cleaned")
            self._context = None

    def _del_timeout(self):
        if self._timeout_source:
            self._timeout_source.destroy()
            self._timeout_source = None

    def register_async(self, action, fast=False):
        """
        Register action(string) to wait list.
        Set fast as True if requested action does not require too much time,
        for example: profile modification.
        """
        queue = self._fast_queue if fast else self._slow_queue
        max_queue = FAST_ASYNC_QUEUE_SIZE if fast else SLOW_ASYNC_QUEUE_SIZE
        if len(queue) >= max_queue:
            logging.debug(
                f"Async queue({max_queue}) full, waiting all existing actions "
                "to be finished before registering more async action"
            )
            # TODO: No need to wait all finish, should continue when the queue
            #       is considerably empty and ready for new async action.
            self.wait_all_finish()

        if action in self._fast_queue or action in self._slow_queue:
            raise NmstateInternalError(
                f"BUG: An existing actions {action} is already registered"
            )

        logging.debug(f"Async action: {action} started")
        queue.add(action)

    def finish_async(self, action, suppress_log=False):
        """
        Mark action(string) as finished.
        """
        self._last_async_finish_time = datetime.datetime.now()
        if not suppress_log:
            logging.debug(f"Async action: {action} finished")
        self._fast_queue.discard(action)
        self._slow_queue.discard(action)

    def _action_all_finished(self):
        return not (len(self._fast_queue) or len(self._slow_queue))

    def _idle_timeout_cb(self, _user_data):
        if self._error or self._action_all_finished():
            return GLib.SOURCE_REMOVE
        idle_time = datetime.datetime.now() - self._last_async_finish_time
        if idle_time > datetime.timedelta(seconds=IDLE_TIMEOUT):
            remaining_actions = self._slow_queue | self._fast_queue
            self.fail(
                NmstateTimeoutError(f"Action {remaining_actions} timeout")
            )
            return GLib.SOURCE_REMOVE
        else:
            return GLib.SOURCE_CONTINUE

    def is_cancelled(self):
        return self._cancellable.is_cancelled()

    def fail(self, exception):
        if not self._cancellable.is_cancelled():
            if self._error:
                logging.error(
                    f"BUG: There is already a exception assigned: "
                    f"existing: {self._error}, new exception {exception}"
                )
            self.cancellable.cancel()
            self._del_timeout()
            self._error = exception

    def wait_all_finish(self):
        """
        Block till all async actions been marked as finished via
        `finish_async()` or anyone failed by `fail()`.
        """
        self._last_async_finish_time = datetime.datetime.now()
        if not self._action_all_finished():
            self._timeout_source = GLib.timeout_source_new(
                IDLE_CHECK_INTERNAL * 1000
            )
            user_data = None
            self._timeout_source.set_callback(self._idle_timeout_cb, user_data)
            self._timeout_source.attach(self._context)

            while not self._action_all_finished() and not self._error:
                self.context.iteration(True)
            self._del_timeout()

        if self._error:
            # The queue and error should be flush and perpare for another run
            self._cancellable.cancel()
            self._init_queue()
            self._init_cancellable()
            tmp_error = self._error
            self._error = None
            # pylint: disable=raising-bad-type
            raise tmp_error
            # pylint: enable=raising-bad-type
