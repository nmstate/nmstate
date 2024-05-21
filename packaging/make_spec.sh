#!/bin/bash

set -e

SRC_DIR="$(dirname "$0")/.."

SPEC_FILE_PATH="${SRC_DIR}/packaging/nmstate.spec"

cp ${SPEC_FILE_PATH}.in ${SPEC_FILE_PATH}

eval "$(${SRC_DIR}/packaging/get_version.sh)"


if [ "CHK$IS_RELEASE" == "CHK1" ];then
    IS_SNAPSHOT=0
    RPM_RELEASE=1
else
    IS_SNAPSHOT=1
fi

sed -i \
    -e "s/@IS_SNAPSHOT@/${IS_SNAPSHOT}/" \
    -e "s/@VERSION@/${RPM_VERSION}/" \
    -e "s/@RELEASED_VERSION@/${RELEASED_VERSION}/" \
    -e "s/@RELEASE@/${RPM_RELEASE}/" \
    -e "s/@CHANGELOG@/${RPM_CHANGELOG}/" \
    $SPEC_FILE_PATH
