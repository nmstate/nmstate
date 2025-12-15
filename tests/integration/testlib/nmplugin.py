# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
from subprocess import CalledProcessError
from time import sleep

from . import cmdlib


@contextmanager
def disable_nm_plugin(plugin):
    try:
        _, rpm_output, _ = cmdlib.exec_cmd(
            ("rpm", "-ql", f"NetworkManager-{plugin}"), check=True
        )
    except CalledProcessError:
        yield
    else:
        lib_path = [lib for lib in rpm_output.split() if lib.endswith(".so")][
            0
        ]
        with mount_devnull_to_path(lib_path):
            yield


@contextmanager
def mount_devnull_to_path(lib_path):
    try:
        cmdlib.exec_cmd(("mount", "--bind", "/dev/null", lib_path), check=True)
        with nm_service_restart():
            try:
                yield
            finally:
                cmdlib.exec_cmd(("umount", lib_path), check=True)
    except CalledProcessError:
        cmdlib.exec_cmd(("umount", lib_path), check=True)
        raise


@contextmanager
def nm_service_restart():
    # If we restart too often, systemd will not start NetworkManager due to
    # 'start-limit-hit'. Resetting failure count will helps here.
    cmdlib.exec_cmd(
        "systemctl reset-failed NetworkManager.service".split(), check=False
    )
    systemctl_restart_nm_cmd = ("systemctl", "restart", "NetworkManager")
    cmdlib.exec_cmd(systemctl_restart_nm_cmd, check=True)
    # Wait 2 seconds for NetworkManager to start.
    sleep(2)
    try:
        yield
    finally:
        cmdlib.exec_cmd(systemctl_restart_nm_cmd, check=True)
        # Wait 2 seconds for NetworkManager to start.
        sleep(2)
