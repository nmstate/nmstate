#
# Copyright 2014-2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division
from contextlib import contextmanager
from functools import partial
import threading

from six.moves import queue

from . import libnl

_POOL_SIZE = 5

_NL_SOCKET_BUFF_SIZE = 1024 * 512


_tls = threading.local()


class NLSocketPool(object):
    """Pool of netlink sockets."""
    def __init__(self, size):
        if size <= 0:
            raise ValueError('Invalid socket pool size %r. Must be positive')
        self._semaphore = threading.BoundedSemaphore(size)
        self._sockets = queue.Queue(maxsize=size)

    @contextmanager
    def socket(self):
        """Returns a socket from the pool (creating it when needed)."""
        if hasattr(_tls, 'socket'):
            yield _tls.socket
        else:
            with self._semaphore:
                _tls.socket = self._get_socket()
                try:
                    yield _tls.socket
                finally:
                    self._put_socket(_tls.socket)
                    del _tls.socket

    def _get_socket(self):
        try:
            socket = self._sockets.get_nowait()
        except queue.Empty:
            socket = _open_socket()
        return socket

    def _put_socket(self, socket):
        self._sockets.put_nowait(socket)


_pool = NLSocketPool(_POOL_SIZE)


def _open_socket(callback_function=None, callback_arg=None):
    """Returns an open netlink socket.
        callback_function: Modify the callback handler associated with the
        socket. Callback function requires two arguments:
            nl_message: netlink message passed by the socket
            args: optional argument defined by _nl_socket_modify_cb()
        callback_arg: optional argument passed to the callback function
    """
    sock = libnl.nl_socket_alloc()
    try:
        if callback_function is not None:
            libnl.nl_socket_disable_seq_check(sock)
            libnl.nl_socket_modify_cb(sock, libnl.NlCbKind.NL_CB_DEFAULT,
                                      libnl.NlCbKind.NL_CB_CUSTOM,
                                      callback_function, callback_arg)

        libnl.nl_connect(sock, libnl.NETLINK_ROUTE)
        libnl.nl_socket_set_buffer_size(sock, _NL_SOCKET_BUFF_SIZE, 0)
    except:
        libnl.nl_socket_free(sock)
        raise
    return sock


def _close_socket(sock):
    """Closes and frees the resources of the passed netlink socket."""
    libnl.nl_socket_free(sock)


@contextmanager
def _cache_manager(cache_allocator, sock):
    """Provides a cache using cache_allocator and frees it and its links upon
    exit."""
    cache = cache_allocator(sock)
    try:
        yield cache
    finally:
        libnl.nl_cache_free(cache)


def _socket_memberships(socket_membership_function, socket, groups):
    groups_codes = [libnl.GROUPS[g] for g in groups]
    groups_codes = groups_codes + [0] * (
        len(libnl.GROUPS) - len(groups_codes) + 1)
    try:
        socket_membership_function(socket, *groups_codes)
    except:
        libnl.nl_socket_free(socket)
        raise

_add_socket_memberships = partial(_socket_memberships,
                                  libnl.nl_socket_add_memberships)
_drop_socket_memberships = partial(_socket_memberships,
                                   libnl.nl_socket_drop_memberships)
