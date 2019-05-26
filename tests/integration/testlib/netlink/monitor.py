# Copyright 2014-2019 Red Hat, Inc.
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

from contextlib import closing, contextmanager
import errno
import logging
import os
import select
import sys
import threading

import six
from six.moves import queue

from ..thread import thread

from . import (_add_socket_memberships,
               _close_socket, _drop_socket_memberships, _open_socket)
from . import libnl
from .addr import _addr_info
from .link import _link_info
from .route import _route_info


E_NOT_RUNNING = 1
E_TIMEOUT = 2


class EventType(object):
    DATA = 0
    EXCEPTION = 30
    STOP = 31
    TIMEOUT = 32


class Event(object):
    def __init__(self, type, data=None):
        self.type = type
        self.data = data or {}


class MonitorError(Exception):
    pass


class Monitor(object):
    """Netlink monitor. Usage:

    Get events collected while the monitor was running:
    mon = Monitor()
    mon.start()
    ...
    mon.stop()
    for event in mon:
        handle event
    mon.wait()

    Monitoring events synchronously:
    mon = Monitor()
    mon.start()
    for event in mon:
        if foo:
            mon.stop()
        handle event
    mon.wait()

    Monitoring events with defined timeout. If timeout expires during
    iteration and silent_timeout is set to False, MonitorError(E_TIMEOUT) is
    raised by iteration:
    mon = Monitor(timeout=2)
    mon.start()
    for event in mon:
        handle event
    mon.wait()

    Monitor defined groups (monitor everything if not set):
    mon = Monitor(groups=('link', 'ipv4-route'))
    mon.start()
    for event in mon:
        if foo:
            mon.stop()
        handle event
    mon.wait()

    Possible groups: link, notify, neigh, tc, ipv4-ifaddr, ipv4-mroute,
    ipv4-route, ipv6-ifaddr, ipv6-mroute, ipv6-route, ipv6-ifinfo,
    decnet-ifaddr, decnet-route, ipv6-prefix
    """
    def __init__(self, groups=frozenset(), timeout=None, silent_timeout=False):
        self._time_start = None
        self._timeout = timeout
        self._silent_timeout = silent_timeout
        if groups:
            unknown_groups = frozenset(groups).difference(
                frozenset(libnl.GROUPS))
            if unknown_groups:
                raise AttributeError('Invalid groups: %s' % (unknown_groups,))
            self._groups = groups
        else:
            self._groups = frozenset(libnl.GROUPS.keys())
        self._queue = queue.Queue()
        self._scan_thread = thread(self._scan, name='netlink/events')
        self._scanning_started = threading.Event()
        self._scanning_stopped = threading.Event()

    def __iter__(self):
        for event in iter(self._queue.get, None):
            if event.type == EventType.TIMEOUT:
                if self._silent_timeout:
                    break
                raise MonitorError(E_TIMEOUT)
            elif event.type == EventType.STOP:
                break
            elif event.type == EventType.EXCEPTION:
                _, val, tb = event.data
                six.reraise(MonitorError, MonitorError(val), tb)

            yield event.data

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if not self.is_stopped():
            self.stop()
        self.wait()

    def start(self):
        if self._timeout:
            self._end_time = _monotonic_time() + self._timeout
        self._scan_thread.start()
        self._scanning_started.wait()

    def _scan(self):
        try:
            epoll = select.epoll()
            with closing(epoll):
                with _monitoring_socket(
                        self._queue, self._groups, epoll) as sock:
                    with _pipetrick(epoll) as self._pipetrick:
                        self._scanning_started.set()
                        while True:
                            if self._timeout:
                                timeout = self._end_time - _monotonic_time()
                                # timeout expired
                                if timeout <= 0:
                                    self._scanning_stopped.set()
                                    self._queue.put(Event(EventType.TIMEOUT))
                                    break
                            else:
                                timeout = -1

                            events = _uninterruptible_poll(epoll.poll,
                                                           timeout=timeout)
                            # poll timeouted
                            if len(events) == 0:
                                self._scanning_stopped.set()
                                self._queue.put(Event(EventType.TIMEOUT))
                                break
                            # stopped by pipetrick
                            elif (self._pipetrick[0], select.POLLIN) in events:
                                _uninterruptible(
                                    os.read, self._pipetrick[0], 1)
                                self._queue.put(Event(EventType.STOP))
                                break

                            libnl.nl_recvmsgs_default(sock)
        except:
            event = Event(EventType.EXCEPTION, sys.exc_info())
            self._queue.put(event)
            raise

    def stop(self):
        if self.is_stopped():
            raise MonitorError(E_NOT_RUNNING)
        else:
            self._scanning_stopped.set()
            self._scanning_started.wait()
            os.write(self._pipetrick[1], b'c')

    def is_stopped(self):
        return self._scanning_stopped.is_set()

    def wait(self):
        self._scan_thread.join()


def _object_input(obj, queue):
    """This function serves as a callback for nl_msg_parse(message, callback,
    extra_argument) function. When nl_msg_parse() is called, it passes message
    as an object to defined callback with optional extra argument (monitor's
    queue in our case)
    """
    obj_type = libnl.nl_object_get_type(obj)
    obj_dict = None
    if obj_type == libnl.RtnlObjectType.ADDR:
        obj_dict = _addr_info(obj)
    elif obj_type == libnl.RtnlObjectType.LINK:
        obj_dict = _link_info(obj)
    elif obj_type.split('/', 1)[0] == libnl.RtnlObjectType.BASE:
        obj_dict = _route_info(obj)

    if obj_dict is not None:
        msg_type = libnl.nl_object_get_msgtype(obj)
        try:
            obj_dict['event'] = libnl.EVENTS[msg_type]
        except KeyError:
            logging.error('unexpected msg_type %s', msg_type)
        else:
            queue.put(Event(EventType.DATA, obj_dict))
_c_object_input = libnl.prepare_cfunction_for_nl_msg_parse(_object_input)


def _event_input(msg, c_queue):
    """This function serves as a callback for netlink socket. When socket
    recieves a message, it passes it to callback function with optional extra
    argument (monitor's queue in this case)
    """
    libnl.nl_msg_parse(msg, _c_object_input, c_queue)
    return libnl.NlCbAction.NL_STOP
_c_event_input = libnl.prepare_cfunction_for_nl_socket_modify_cb(_event_input)


@contextmanager
def _monitoring_socket(queue, groups, epoll):
    c_queue = libnl.c_object_argument(queue)
    sock = _open_socket(callback_function=_c_event_input, callback_arg=c_queue)
    try:
        _add_socket_memberships(sock, groups)
        try:
            fd = libnl.nl_socket_get_fd(sock)
            epoll.register(fd, select.EPOLLIN)
            try:
                yield sock
            finally:
                epoll.unregister(fd)
        finally:
            _drop_socket_memberships(sock, groups)
    finally:
        _close_socket(sock)


@contextmanager
def _pipetrick(epoll):
    pipetrick = os.pipe()
    try:
        epoll.register(pipetrick[0], select.EPOLLIN)
        try:
            yield pipetrick
        finally:
            epoll.unregister(pipetrick[0])
    finally:
        os.close(pipetrick[0])
        os.close(pipetrick[1])


def _uninterruptible(func, *args, **kwargs):
    """
    Call func with *args and *kwargs and return the result, retrying if func
    failed with EINTR. This may happen if func invoked a system call and the
    call was interrupted by signal.

    WARNING: Use only with functions which are safe to restart after EINTR.
    """
    while True:
        try:
            return func(*args, **kwargs)
        except EnvironmentError as e:
            if e.errno != errno.EINTR:
                raise


def _uninterruptible_poll(pollfun, timeout=-1):
    """
    This wrapper is used to handle the interrupt exceptions that might
    occur during a poll system call. The wrapped function must be defined
    as poll([timeout]) where the special timeout value 0 is used to return
    immediately and -1 is used to wait indefinitely.
    """
    # When the timeout < 0 we shouldn't compute a new timeout after an
    # interruption.
    endtime = None if timeout < 0 else _monotonic_time() + timeout

    while True:
        try:
            return pollfun(timeout)
        except (IOError, select.error) as e:
            if e.args[0] != errno.EINTR:
                raise

        if endtime is not None:
            timeout = max(0.0, endtime - _monotonic_time())


def _monotonic_time():
    """
    Return the amount of time, in secs, elapsed since a fixed
    arbitrary point in time in the past.
    This function is useful if the client just
    needs to use the difference between two given time points.

    With respect to time.time():
    * The resolution of this function is lower. On Linux,
      the resolution is 1/_SC_CLK_TCK, which in turn depends on
      the value of HZ configured in the kernel. A commonly
      found resolution is 10 (ten) ms.
    * This function is resilient with respect to system clock
      adjustments.
    """
    return os.times()[4]
