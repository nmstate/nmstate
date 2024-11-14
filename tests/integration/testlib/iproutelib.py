# SPDX-License-Identifier: LGPL-2.1-or-later

from contextlib import contextmanager
from functools import wraps
from tempfile import TemporaryFile
import json
import subprocess
import time

from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType

from .cmdlib import exec_cmd
from .statelib import show_only


def ip_monitor_assert_stable_link_up(dev):
    def decorator(func):
        @wraps(func)
        def wrapper_ip_monitor(*args, **kwargs):
            iface_state = show_only((dev,))[Interface.KEY][0]
            assert iface_state[Interface.TYPE] not in [
                InterfaceType.ETHERNET,
                InterfaceType.VETH,
            ]
            with TemporaryFile() as fd:
                with ip_monitor(fd):
                    func(*args, **kwargs)
                result = fd.read().decode()
                assert (
                    len(get_non_up_events(result, dev)) == 0
                ), f"result: {result}"

        return wrapper_ip_monitor

    return decorator


@contextmanager
def ip_monitor(fd):
    # The link might not created yet before test function starts, hence
    # we monitor on all links.
    p = subprocess.Popen(
        "ip monitor link".split(),
        close_fds=True,
        stdout=fd,
        env=None,
    )
    # Wait ip monitor to be started
    time.sleep(1)
    yield
    fd.flush()
    fd.seek(0)
    p.terminate()


def get_non_up_events(content, dev):
    """
    Check whether ip monitor output contains lines other than "state UP"
    """
    return [
        line
        for line in content.split("\n")
        if "state UP" not in line and dev in line
    ]


def iproute_get_ip_addrs_with_order(iface, is_ipv6):
    """
    Return a list of ip address with the order reported by ip route
    """
    family = 6 if is_ipv6 else 4
    output = json.loads(
        exec_cmd(f"ip -d -j -{family} addr show dev {iface}".split())[1]
    )
    return [addr_info["local"] for addr_info in output[0]["addr_info"]]
