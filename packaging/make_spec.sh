#!/bin/bash

set -e

SRC_DIR="$(dirname "$0")/.."

eval "$(${SRC_DIR}/packaging/get_version.sh)"

# spec variable is used by COPR as well: https://docs.pagure.org/copr.copr/user_documentation.html
if [ -z "${spec}" ]; then
    if [ -n "$(rpm -E %{?fedora} 2>/dev/null)" ] ||
       [ -n "$(rpm -E %{?el8} 2>/dev/null)" ]; then
        pysuffix=.py3
    elif [ -n "$(rpm -E %{?el7} 2>/dev/null)" ]; then
        pysuffix=.py2
    else
        echo "Not supported" >&2
        exit 1
    fi
    spec="${SRC_DIR}/packaging/nmstate${pysuffix}.spec"
fi


sed \
    -e "s/@VERSION@/${RPM_VERSION}/" \
    -e "s/@RELEASE@/${RPM_RELEASE}/" \
    -e "s/@CHANGELOG@/${RPM_CHANGELOG}/" \
    "${spec}"
