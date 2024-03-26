# SPDX-License-Identifier: LGPL-2.1-or-later

import subprocess
import sys
import setuptools


def requirements():
    req = []
    with open("requirements.txt") as fd:
        for line in fd:
            line.strip()
            if not line.startswith("#"):
                req.append(line)
    return req


def install_nmstate_lib():
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "nmstate"]
        )
    except subprocess.CalledProcessError as e:
        print("Error installing nmstate C library:", e)
        sys.exit(1)


try:
    import nmstate  # noqa: F401

    print("nmstate C library found. No further action needed.")
except ImportError:
    print("nmstate C library not found. Attempting to install...")
    install_nmstate_lib()

setuptools.setup(
    name="nmstate",
    version="2.2.28",
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
