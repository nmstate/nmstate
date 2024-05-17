# SPDX-License-Identifier: LGPL-2.1-or-later
import ctypes
import sys
import setuptools
import subprocess


def requirements():
    req = []
    with open("requirements.txt", encoding="utf-8") as fd:
        for line in fd:
            line.strip()
            if not line.startswith("#"):
                req.append(line)
    return req


def check_nmstate_c_library():
    if "bdist_rpm" not in sys.argv:
        try:
            # Run the find command
            result = subprocess.run(
                ["find", "/", "-name", "libnmstate.so.2"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            # Check if the command was successful
            if result.returncode == 0:
                # Print the result
                print("-----Found files:\n", result.stdout)
            else:
                # Print the error if the command failed
                print("----The Error is:\n", result.stderr)
            ctypes.cdll.LoadLibrary("libnmstate.so.2")
        except OSError as exc:
            raise RuntimeError(
                "Error: nmstate C library not found. "
                "Please install nmstate C library separately "
                "before installing the Python package."
                "See: https://nmstate.io/user/install.html"
            ) from exc


check_nmstate_c_library()


setuptools.setup(
    name="nmstate",
    version="2.2.32",
    author="Gris Ge",
    author_email="fge@redhat.com",
    description="Python binding of nmstate",
    long_description="Python binding of nmstate",
    url="https://github.com/nmstate/nmstate/",
    packages=setuptools.find_packages(),
    install_requires=requirements(),
    license="ASL2.0+",
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
)
