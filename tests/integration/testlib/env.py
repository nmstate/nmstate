# SPDX-License-Identifier: LGPL-2.1-or-later

import os

from .cmdlib import exec_cmd


def is_fedora():
    return os.path.exists("/etc/fedora-release")


def is_ubuntu_kernel():
    return "Ubuntu" in os.uname().version


def nm_minor_version():
    version_str = exec_cmd(
        "rpm -q NetworkManager --qf %{VERSION}".split(),
        check=True,
    )[1]
    return int(version_str.split(".")[1])


def is_k8s():
    return os.getenv("RUN_K8S") == "true"


def is_el8():
    return exec_cmd("rpm -E %{?rhel}".split())[1].strip() == "8"


def nm_libreswan_version_int():
    version_str = exec_cmd(
        "rpm -q NetworkManager-libreswan --qf %{VERSION}".split(),
        check=True,
    )[1]
    return version_str_to_int(version_str)


def version_str_to_int(version_str):
    versions = version_str.split(".")
    return int(versions[0]) * 10000 + int(versions[1]) * 100 + int(versions[2])
