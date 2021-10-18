#!/bin/bash

set -e

SRC_DIR="$(dirname "$0")/.."
TMP_DIR=$(mktemp -d)
OLD_PWD=$(pwd)

trap 'rm -rf "$TMP_DIR"' INT TERM HUP EXIT

cd $SRC_DIR

eval "$(./packaging/get_version.sh)"

SRPM_FILE="$(./packaging/make_srpm.sh)"

TAR_FILE="${TMP_DIR}/nmstate-${VERSION}.tar"
(
    rpmbuild --define "_rpmdir $TMP_DIR/" --define "_srcrpmdir $TMP_DIR/" \
    --rebuild "${SRPM_FILE}"
) > /dev/stderr
RPMS=`find $TMP_DIR -type f \
    \( -name \*.noarch.rpm -o -name \*.x86_64.rpm \) -exec basename {} \;`
find $TMP_DIR -type f -name \*.rpm -exec mv {} $OLD_PWD \;
for RPM in $RPMS; do
    echo -n "$OLD_PWD/$RPM "
done
