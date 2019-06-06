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

from contextlib import contextmanager
import subprocess
import threading
import time

import six


TIMEOUT = 10


class IpMonitorResult(object):
    def __init__(self):
        self.out = None
        self.err = None
        self.popen = None


def ip_monitor_assert_stable_link_up(dev, timeout=10):
    def decorator(func):
        @six.wraps(func)
        def wrapper_ip_monitor(*args, **kwargs):
            with ip_monitor('link', dev, timeout) as result:
                func(*args, **kwargs)
            assert len(get_non_up_events(result, dev)) == 0, ('result: ' +
                                                              result.out)
        return wrapper_ip_monitor
    return decorator


@contextmanager
def ip_monitor(object_type, dev, timeout=10):
    result = IpMonitorResult()

    cmds = 'timeout {} ip monitor {} dev {}'.format(timeout, object_type, dev)

    def run():
        result.popen = subprocess.Popen(
            cmds.split(),
            close_fds=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=None
        )
        result.out, result.err = result.popen.communicate(None)
        result.out = result.out.decode('utf-8')
        result.err = result.err.decode('utf-8')

    def finalize():
        if result.popen:
            result.popen.terminate()

    with _thread(run, 'ip-monitor', teardown_cb=finalize):
        # Let the ip monitor thread start before proceeding to the action.
        time.sleep(1)
        yield result


def get_non_up_events(result, dev):
    """
    Given a result and device, filter only the non UP events (DOWN, UNKNOWN)
    and return them as a list.
    :param result: IpMonitorResult
    :return: List of non UP events
    """
    return [l for l in result.out.split('\n')
            if 'state UP' not in l and dev in l]


@contextmanager
def _thread(func, name, teardown_cb=lambda: None):
    t = threading.Thread(target=func, name=name)
    t.daemon = True
    t.start()
    try:
        yield t
    finally:
        teardown_cb()
        t.join()
