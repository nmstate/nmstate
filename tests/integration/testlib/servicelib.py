# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import time

from . import cmdlib


@contextmanager
def disable_service(service):
    cmdlib.exec_cmd(("systemctl", "stop", service), check=True)
    # Wait service actually stopped
    ret, _, _ = cmdlib.exec_cmd(("systemctl", "status", service), check=False)
    timeout = 5
    while timeout > 0:
        if ret != 0:
            break
        time.sleep(1)
        timeout -= 1
        ret, _, _ = cmdlib.exec_cmd(
            ("systemctl", "status", service), check=False
        )
    try:
        yield
    finally:
        cmdlib.exec_cmd(("systemctl", "start", service), check=True)
        ret, _, _ = cmdlib.exec_cmd(("systemctl", "status", service))
        timeout = 5
        while timeout > 0:
            if ret == 0:
                break
            time.sleep(1)
            timeout -= 1
            ret, _, _ = cmdlib.exec_cmd(("systemctl", "status", service))
