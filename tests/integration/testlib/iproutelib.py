#
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

from contextlib import contextmanager
from functools import wraps
import json
import subprocess
import threading
import time

from .cmdlib import exec_cmd


TIMEOUT = 10


class IpMonitorResult:
    def __init__(self):
        self.out = None
        self.err = None
        self.popen = None


def ip_monitor_assert_stable_link_up(dev, timeout=10):
    def decorator(func):
        @wraps(func)
        def wrapper_ip_monitor(*args, **kwargs):
            with ip_monitor("link", dev, timeout) as result:
                func(*args, **kwargs)
            assert len(get_non_up_events(result, dev)) == 0, (
                "result: " + result.out
            )

        return wrapper_ip_monitor

    return decorator


@contextmanager
def ip_monitor(object_type, dev, timeout=10):
    result = IpMonitorResult()

    cmds = "timeout {} ip monitor {} dev {}".format(timeout, object_type, dev)

    def run():
        result.popen = subprocess.Popen(
            cmds.split(),
            close_fds=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=None,
        )
        result.out, result.err = result.popen.communicate(None)
        result.out = result.out.decode("utf-8")
        result.err = result.err.decode("utf-8")

    def finalize():
        if result.popen:
            result.popen.terminate()

    with _thread(run, "ip-monitor", teardown_cb=finalize):
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
    return [
        line
        for line in result.out.split("\n")
        if "state UP" not in line and dev in line
    ]


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


def iproute_get_ip_addrs_with_order(iface, is_ipv6):
    """
    Return a list of ip address with the order reported by ip route
    """
    family = 6 if is_ipv6 else 4
    output = json.loads(
        exec_cmd(f"ip -d -j -{family} addr show dev {iface}".split())[1]
    )
    return [addr_info["local"] for addr_info in output[0]["addr_info"]]
