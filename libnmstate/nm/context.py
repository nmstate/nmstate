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
import sys
import logging

from .common import NM
from .common import GLib


class NmContext:
    def __init__(self):
        self._cli = NM.Client.new(cancellable=None)
        self._quiting = False

    @property
    def client(self):
        if self._quiting:
            logging.debug("BUG: Access NM.Client when it is cleaning up")
        return self._cli

    def __del__(self):
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
            context = self._cli.get_main_context()
            self._cli.get_context_busy_watcher().weak_ref(
                lambda: is_done.append(1)
            )
            self._cli = None
            self._quiting = True

            while context.iteration(False):
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
                    timeout_source.attach(context)
                    while not is_done:
                        context.iteration(True)
                finally:
                    timeout_source.destroy()
