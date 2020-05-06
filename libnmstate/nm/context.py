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
import logging

from .common import NM
from .common import GLib


class NmContext:
    def __init__(self):
        self._client = NM.Client.new(cancellable=None)
        self._context = self._client.get_main_context()
        self._quitting = False

    @property
    def client(self):
        if self._quitting:
            return None
        return self._client

    @property
    def context(self):
        return self._context

    def refresh_content(self):
        if self.context:
            while self.context.iteration(False):
                pass

    def clean_up(self):
        self._del_client()

    def _del_client(self):
        if self._client:
            is_done = []
            is_timeout = []
            self._client.get_context_busy_watcher().weak_ref(
                lambda: is_done.append(1)
            )
            self._client = None
            self._quitting = True

            self.refresh_content()

            if not is_done:
                timeout_source = GLib.timeout_source_new(50)
                try:
                    timeout_source.set_callback(lambda x: is_timeout.append(1))
                    timeout_source.attach(self._context)
                    while not is_done and not is_timeout:
                        self._context.iteration(True)
                finally:
                    timeout_source.destroy()

            if not is_done:
                logging.error("BUG: NM.Client is not cleaned")
            self._context = None
