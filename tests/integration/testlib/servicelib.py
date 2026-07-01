# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import time

from . import cmdlib


def _wait_until(cmd, want_success, timeout=5):
    while timeout > 0:
        ret, _, _ = cmdlib.exec_cmd(cmd, check=False)
        if (ret == 0) == want_success:
            return
        time.sleep(1)
        timeout -= 1


@contextmanager
def disable_service(service):
    cmdlib.exec_cmd(("systemctl", "stop", service), check=True)
    _wait_until(("systemctl", "status", service), want_success=False)
    try:
        yield
    finally:
        # A rapid stop/start cycle trips systemd's start-limit, leaving the
        # unit unactivatable; reset-failed clears the counter before start.
        cmdlib.exec_cmd(("systemctl", "reset-failed", service), check=False)
        cmdlib.exec_cmd(("systemctl", "start", service), check=True)
        _wait_until(("systemctl", "status", service), want_success=True)
        # systemd reports NetworkManager active before it claims its D-Bus
        # name; wait for it to answer so callers do not hit "not activatable".
        if service == "NetworkManager":
            _wait_until(
                ("nmcli", "general", "status"),
                want_success=True,
                timeout=10,
            )
