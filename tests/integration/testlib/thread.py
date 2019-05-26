#
# Copyright 2019 Red Hat, Inc.
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

import ctypes
import logging
import threading


NAME_MAX_LENGTH = 15

_LIBPTHREAD = ctypes.CDLL("libpthread.so.0", use_errno=True)

_pthread_setname_np_proto = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_ulong, ctypes.c_char_p)

try:
    _pthread_setname_np = _pthread_setname_np_proto(('pthread_setname_np',
                                                    _LIBPTHREAD))
except AttributeError:
    def _pthread_setname_np(ident, name):
        pass

    logging.warning(
        'pthread_setname_np unavailable. '
        'System thread names will not be set.')


def thread(func, args=(), kwargs=None, name=None):
    """
    Create a thread for runnning func with args.

    Arguments:

    func        Function to run in a new thread.

    args        Arguments to pass to func

    kwargs      Keyword arguments to pass to func

    name        If set, set thread name.
    """
    if kwargs is None:
        kwargs = {}

    def run():
        thread = threading.current_thread()
        try:
            logging.debug("START thread %s (func=%s, args=%s, kwargs=%s)",
                      thread, func, args, kwargs)
            _setname(thread.name[:15])
            ret = func(*args, **kwargs)
            logging.debug("FINISH thread %s", thread)
            return ret
        except (SystemExit, KeyboardInterrupt) as e:
            # Unlikley, but not interesting.
            logging.debug("FINISH thread %s (%s)", thread, e)
        except:
            logging.exception("FINISH thread %s failed", thread)

    t = threading.Thread(target=run, name=name)
    t.daemon = True
    return t


def _setname(name):
    """
    Set a system-wide thread name.

    The most common use of this function is inside a thread target function:

        def run():
            pthread.setname("vdsm-cleanup")
            ...

        Thread(target=run).start()

    The name is limited to 15 ASCII characters - see pthread_setname_np(3).
    """
    NAME_MAX_LENGTH = 15

    name = name.encode("ascii")
    if len(name) > NAME_MAX_LENGTH:
        raise ValueError("Expecting up to %d bytes for the name" % (
            NAME_MAX_LENGTH))

    thread = threading.current_thread()
    _pthread_setname_np(thread.ident, name)
