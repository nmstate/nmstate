# SPDX-License-Identifier: Apache-2.0

import os

from .cmdlib import exec_cmd


def is_fedora():
    return os.path.exists("/etc/fedora-release")


def is_el10():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.strip() == 'PLATFORM_ID="platform:el10"':
                    return True
    except FileNotFoundError:
        pass
    return False


def nm_minor_version():
    version_str = exec_cmd(
        "rpm -q NetworkManager --qf %{VERSION}".split(),
        check=True,
    )[1]
    return int(version_str.split(".")[1])


def is_k8s():
    return os.getenv("RUN_K8S") == "true"


def nm_libreswan_version_int():
    ret_code, version_str, _ = exec_cmd(
        "rpm -q NetworkManager-libreswan --qf %{VERSION}".split()
    )
    if ret_code != 0:
        return 0
    return version_str_to_int(version_str)


def version_int(major, minor, micro=0):
    return major * 10000 + minor * 100 + micro


def version_str_to_int(version_str):
    versions = version_str.split(".")
    return version_int(int(versions[0]), int(versions[1]), int(versions[2]))


def kernel_newer_than(major, minor):
    version_str = exec_cmd("uname -r".split(), check=True)[1].split("-")[0]
    return version_str_to_int(version_str) >= version_int(major, minor)
