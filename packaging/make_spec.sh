#!/bin/bash

set -e

SRC_DIR="$(dirname "$0")/.."

eval "$(${SRC_DIR}/packaging/get_version.sh)"

# spec variable is used by COPR as well: https://docs.pagure.org/copr.copr/user_documentation.html
if [ -z "${spec}" ]; then
    spec="${SRC_DIR}/packaging/nmstate.spec"
fi


sed \
    -e "s/@VERSION@/${RPM_VERSION}/" \
    -e "s/@RELEASE@/${RPM_RELEASE}/" \
    -e "s/@CHANGELOG@/${RPM_CHANGELOG}/" \
    "${spec}"
