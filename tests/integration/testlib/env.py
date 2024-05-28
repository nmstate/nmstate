# SPDX-License-Identifier: LGPL-2.1-or-later

import os

import gi

from .cmdlib import exec_cmd

gi.require_version("NM", "1.0")
# It is required to state the NM version before importing it
# But this break the flak8 rule: https://www.flake8rules.com/rules/E402.html
# Use NOQA: E402 to suppress it.
# pylint: disable=no-name-in-module
from gi.repository import NM  # NOQA: E402

# pylint: enable=no-name-in-module


def is_fedora():
    return os.path.exists("/etc/fedora-release")


def is_ubuntu_kernel():
    return "Ubuntu" in os.uname().version


def nm_major_minor_version():
    return float(f"{NM.MAJOR_VERSION}.{NM.MINOR_VERSION}")


def nm_minor_version():
    return int(f"{NM.MINOR_VERSION}")


def is_k8s():
    return os.getenv("RUN_K8S") == "true"


def is_el8():
    return exec_cmd("rpm -E %{?rhel}".split())[1].strip() == "8"


def nm_libreswan_micro_version():
    return int(
        exec_cmd("rpm -q NetworkManager-libreswan --qf %{VERSION}".split())[1]
        .split(".")[-1]
        .strip()
    )
