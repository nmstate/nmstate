# SPDX-License-Identifier: Apache-2.0

import glob
import os
import time
from pathlib import Path

from .cmdlib import exec_cmd


def get_sriov_vf_names(pf_name):
    ret = []
    for folder in glob.glob(f"/sys/class/net/{pf_name}/device/virtfn*/net/"):
        ret.extend(os.listdir(folder))
    return ret


def read_sriov_totalvfs(pf_name):
    try:
        with open(f"/sys/class/net/{pf_name}/device/sriov_totalvfs") as fd:
            return int(fd.read())
    except OSError:
        return 0


def read_sriov_numvfs(pf_name):
    try:
        with open(f"/sys/class/net/{pf_name}/device/sriov_numvfs") as fd:
            return int(fd.read())
    except OSError:
        return 0


def write_sriov_numvfs(pf_name, count):
    with open(f"/sys/class/net/{pf_name}/device/sriov_numvfs", "w") as fd:
        fd.write(str(count))


def _wait_for_vfs(pf_name, count, timeout, poll_interval):
    """
    Blocks until all VFs for the given PF have an initialized netdev
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = 0
        for vf_id in range(count):
            vf_net_dir = Path(
                f"/sys/class/net/{pf_name}/device/virtfn{vf_id}/net"
            )
            try:
                if vf_net_dir.is_dir() and os.listdir(vf_net_dir):
                    ready += 1
            except OSError:
                pass
        if ready == count:
            return

        time.sleep(poll_interval)

    raise TimeoutError(
        f"Timed out after {timeout}s waiting for {count} VFs on {pf_name}"
    )


def _wait_for_vfs_cleared(pf_name, timeout, poll_interval):
    """
    Blocks until no VF netdev is left for the given PF
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        cleared = True
        for vf_net_dir in glob.glob(
            f"/sys/class/net/{pf_name}/device/virtfn*/net"
        ):
            try:
                if os.listdir(vf_net_dir):
                    cleared = False
                    break
            except OSError:
                pass
        if cleared:
            return

        time.sleep(poll_interval)

    raise TimeoutError(
        f"Timed out after {timeout}s waiting for VFs to be "
        f"cleared on {pf_name}"
    )


def learn_vf_names(pf_name, count):
    """
    VF netdev names depend on the driver and udev, so create the VFs once to
    learn their names, then disable SR-IOV again so the test starts with no
    VF in place.
    """
    pf_dir = Path(f"/sys/class/net/{pf_name}")
    sriov_numvfs = pf_dir / "device" / "sriov_numvfs"

    if not pf_dir.exists():
        raise FileNotFoundError(
            f"Network interface '{pf_name}' does not exist."
        )
    if not sriov_numvfs.exists():
        raise OSError(f"Interface '{pf_name}' does not support SR-IOV.")

    exec_cmd(["ip", "link", "set", pf_name, "up"], check=True)

    # Reset and create VFs
    write_sriov_numvfs(pf_name, 0)
    write_sriov_numvfs(pf_name, count)

    _wait_for_vfs(pf_name, count, 5.0, 1.0)

    vf_names = get_sriov_vf_names(pf_name)

    # Remove the VFs again so the test starts clean
    write_sriov_numvfs(pf_name, 0)
    _wait_for_vfs_cleared(pf_name, 5.0, 1.0)

    return vf_names
